import sqlite3
import pandas as pd
import requests
from tqdm import tqdm
import time
import re
import argparse

# --- Configuration (identical to original) ---
REQUEST_DELAY_SECONDS = 0.2
RESOLUTION_THRESHOLD = 2.0
REQUIRED_METHOD = "X-RAY DIFFRACTION"
COMMIT_BATCH = 500


def read_mmcif_file(pdb_id: str):
    url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.text.splitlines()
    except requests.RequestException:
        return None


def parse_cif_data(cif_lines):
    method, resolution = None, None
    method_pattern = re.compile(r"^\s*_exptl.method\s+'?([^']+)'?")
    for line in cif_lines:
        if line.startswith('_reflns.d_resolution_high'):
            parts = line.split()
            if len(parts) > 1 and parts[1] != '?':
                try:
                    resolution = float(parts[1])
                except (ValueError, IndexError):
                    pass
        match = method_pattern.match(line)
        if match:
            method = match.group(1).strip().upper()
        if method and resolution is not None:
            break
    return {'method': method, 'resolution': resolution}


def ensure_column(db_path):
    with sqlite3.connect(db_path) as conn:
        try:
            # NULL = not yet processed, 0 = processed/not qualifying, 1 = qualifies
            conn.execute('ALTER TABLE invariants ADD COLUMN "2AXR" INTEGER;')
            conn.commit()
            print("Added 2AXR column (NULL = unprocessed).")
        except sqlite3.OperationalError:
            pass  # already exists


def reset_column(db_path):
    print(f"Resetting 2AXR column to NULL for all rows in {db_path}...")
    with sqlite3.connect(db_path, timeout=3600) as conn:
        conn.execute('UPDATE invariants SET "2AXR" = NULL;')
        conn.commit()
    print("Reset complete.")


def run_scraper(db_path):
    start_time = time.time()
    ensure_column(db_path)

    # Checkpoint WAL so reads see latest state
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA wal_checkpoint(FULL);")

    # Only fetch PDB IDs not yet processed (2AXR IS NULL)
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            'SELECT DISTINCT SUBSTR(chain_id, 1, 4) AS pdb_id FROM invariants WHERE "2AXR" IS NULL;',
            conn
        )
        total_done = conn.execute(
            'SELECT COUNT(DISTINCT SUBSTR(chain_id,1,4)) FROM invariants WHERE "2AXR" IS NOT NULL'
        ).fetchone()[0]

    pdb_ids = df['pdb_id'].dropna().tolist()
    print(f"Already processed: {total_done:,}  |  Remaining: {len(pdb_ids):,}")

    if not pdb_ids:
        print("All PDB IDs already processed.")
        return

    qualifying = []
    not_qualifying = []

    for pdb_id in tqdm(pdb_ids, desc="Scraping PDB"):
        cif_lines = read_mmcif_file(pdb_id)
        qualifies = False
        if cif_lines:
            metadata = parse_cif_data(cif_lines)
            if (metadata['method'] == REQUIRED_METHOD and
                    metadata['resolution'] is not None and
                    metadata['resolution'] <= RESOLUTION_THRESHOLD):
                qualifies = True

        if qualifies:
            qualifying.append(pdb_id)
        else:
            not_qualifying.append(pdb_id)

        # Flush to DB every COMMIT_BATCH PDB IDs
        if len(qualifying) + len(not_qualifying) >= COMMIT_BATCH:
            _flush(db_path, qualifying, not_qualifying)
            qualifying, not_qualifying = [], []

        time.sleep(REQUEST_DELAY_SECONDS)

    # Final flush
    if qualifying or not_qualifying:
        _flush(db_path, qualifying, not_qualifying)

    # Report
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        n1 = conn.execute('SELECT COUNT(DISTINCT SUBSTR(chain_id,1,4)) FROM invariants WHERE "2AXR"=1').fetchone()[0]
        n0 = conn.execute('SELECT COUNT(DISTINCT SUBSTR(chain_id,1,4)) FROM invariants WHERE "2AXR"=0').fetchone()[0]
    print(f"\nDone. Qualifying PDB IDs (2AXR=1): {n1:,}  |  Not qualifying: {n0:,}")
    print(f"Total runtime: {time.time() - start_time:.0f}s")


def _flush(db_path, qualifying, not_qualifying):
    with sqlite3.connect(db_path, timeout=600) as conn:
        for batch, value in [(qualifying, 1), (not_qualifying, 0)]:
            for i in range(0, len(batch), 500):
                chunk = batch[i:i+500]
                placeholders = ','.join('?' * len(chunk))
                conn.execute(
                    f'UPDATE invariants SET "2AXR" = {value} WHERE SUBSTR(chain_id, 1, 4) IN ({placeholders})',
                    chunk
                )
        conn.commit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("db_path")
    parser.add_argument("--reset", action="store_true", help="Reset 2AXR to NULL and exit")
    args = parser.parse_args()

    if args.reset:
        reset_column(args.db_path)
    else:
        run_scraper(args.db_path)