"""
Builds a `pdb_resolution` lookup table in the DB with one row per unique PDB ID:
    pdb_id TEXT PRIMARY KEY
    resolution REAL
    is_xray    INTEGER  (1 = X-RAY DIFFRACTION, 0 = other)

Chain-id format: {PDB_ID}-{model}-{entity}-{chain}-{start}-{end}
e.g. 101M-1-1-A-1-154  ->  PDB ID = 101M

Resumable: PDB IDs already present in pdb_resolution are skipped.
"""

import sqlite3
import sys
import os
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

CIF_URL     = "https://files.rcsb.org/download/{}.cif"
MAX_WORKERS = int(os.environ.get('SLURM_CPUS_PER_TASK', 16))
BATCH_SIZE  = 2000


def _fetch(pdb_id: str):
    """Returns (pdb_id, resolution_or_None, is_xray_0_or_1).
    Parses _reflns.d_resolution_high and _exptl.method directly from the CIF
    file, matching the original scraper exactly.
    """
    try:
        r = requests.get(CIF_URL.format(pdb_id.upper()), timeout=30)
        if r.status_code == 404:
            return pdb_id, None, 0
        r.raise_for_status()
        lines = r.text.splitlines()

        method, resolution = None, None
        method_pattern = re.compile(r"^\s*_exptl\.method\s+'?([^']+)'?")
        for line in lines:
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
            if method is not None and resolution is not None:
                break

        is_xray = int(method == 'X-RAY DIFFRACTION')
        return pdb_id, resolution, is_xray

    except Exception as e:
        print(f"  WARN fetch failed {pdb_id}: {e}")
        return pdb_id, None, 0


def main(db_path: str):
    start = time.time()

    with sqlite3.connect(db_path, timeout=7200) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pdb_resolution (
                pdb_id     TEXT PRIMARY KEY,
                resolution REAL,
                is_xray    INTEGER
            );
        """)
        conn.commit()

        # All unique PDB IDs in the invariants table
        all_ids = {
            r[0].upper() for r in conn.execute(
                "SELECT DISTINCT substr(chain_id, 1, instr(chain_id, '-') - 1) FROM invariants"
            ) if r[0]
        }
        # Already fetched
        done_ids = {
            r[0].upper() for r in conn.execute("SELECT pdb_id FROM pdb_resolution")
        }
        todo = sorted(all_ids - done_ids)
        print(f"{len(todo)} PDB IDs to fetch ({len(done_ids)} already cached, {len(all_ids)} total).")

    if not todo:
        print("All PDB IDs already in pdb_resolution.")
        return

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(_fetch, pid): pid for pid in todo}
        n = 0
        for fut in as_completed(futures):
            results.append(fut.result())
            n += 1
            if n % 500 == 0:
                print(f"  Fetched {n}/{len(todo)}...")

    print(f"Writing {len(results)} rows to pdb_resolution...")
    with sqlite3.connect(db_path, timeout=7200) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        for i in range(0, len(results), BATCH_SIZE):
            conn.executemany(
                "INSERT OR REPLACE INTO pdb_resolution (pdb_id, resolution, is_xray) VALUES (?,?,?)",
                results[i:i+BATCH_SIZE],
            )
            conn.commit()

    print(f"Done. Runtime: {time.time()-start:.0f}s")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python add_resolution_flags.py <db_path>")
    main(sys.argv[1])