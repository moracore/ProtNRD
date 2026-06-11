import sqlite3
import pandas as pd
import requests
from tqdm import tqdm
import time
import re
import sys
import argparse

# --- Configuration ---
REQUEST_DELAY_SECONDS = 0.2
RESOLUTION_THRESHOLD = 2.0
REQUIRED_METHOD = "X-RAY DIFFRACTION"

def get_unique_pdb_ids(db_path):
    """Extracts unique 4-character PDB IDs from the invariants table."""
    print("Fetching unique PDB IDs from database...")
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        df = pd.read_sql_query("SELECT DISTINCT SUBSTR(chain_id, 1, 4) AS pdb_id FROM invariants;", conn)
    pdb_ids = df['pdb_id'].dropna().tolist()
    print(f"Found {len(pdb_ids)} unique PDB IDs.")
    return pdb_ids

def read_mmcif_file(pdb_id: str):
    """Downloads the CIF file for a given PDB ID."""
    url = f"https://files.rcsb.org/download/{pdb_id}.cif"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        return response.text.splitlines()
    except requests.RequestException:
        return None

def parse_cif_data(cif_lines):
    """Parses CIF file lines to find experimental method and resolution."""
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

def reset_2axr_column(db_path):
    """Resets the '2AXR' column to 0 for all rows."""
    print(f"Connecting to {db_path} to reset '2AXR' column...")
    with sqlite3.connect(db_path) as conn:
        try:
            conn.execute('UPDATE invariants SET "2AXR" = 0;')
            conn.commit()
            print("Successfully reset '2AXR' column to 0 for all rows.")
            print("Running VACUUM to reclaim space...")
            conn.execute('VACUUM;')
            print("VACUUM complete.")
        except sqlite3.OperationalError as e:
            if "no such column" in str(e):
                 print("Column '2AXR' does not exist. No reset needed.")
            else:
                raise e

def run_scraper(db_path):
    """Main function to run the scraper and update the database directly."""
    start_time = time.time()

    # Ensure the column exists before starting
    with sqlite3.connect(db_path) as conn:
        try:
            conn.execute('ALTER TABLE invariants ADD COLUMN "2AXR" BOOLEAN DEFAULT 0;')
        except sqlite3.OperationalError:
            pass # Column already exists

    pdb_ids = get_unique_pdb_ids(db_path)

    high_quality_pdb_ids = []
    print(f"\nScraping metadata for {len(pdb_ids)} PDB IDs...")

    for pdb_id in tqdm(pdb_ids, desc="Scraping PDB"):
        cif_lines = read_mmcif_file(pdb_id)
        if cif_lines:
            metadata = parse_cif_data(cif_lines)
            if (metadata['method'] == REQUIRED_METHOD and
                metadata['resolution'] is not None and
                metadata['resolution'] <= RESOLUTION_THRESHOLD):
                high_quality_pdb_ids.append(pdb_id)
        time.sleep(REQUEST_DELAY_SECONDS)

    print(f"\nScraping complete. Found {len(high_quality_pdb_ids)} high-quality structures.")

    # Print a sample for verification
    if high_quality_pdb_ids:
        print("\nSample of high-quality PDB IDs found:")
        for pid in high_quality_pdb_ids[:5]:
            print(f"- {pid}")

    if high_quality_pdb_ids:
        print("\nUpdating database... (This may take a moment)")
        with sqlite3.connect(db_path, timeout=7200) as conn:
            batch_size = 500
            for i in tqdm(range(0, len(high_quality_pdb_ids), batch_size), desc="Updating DB"):
                batch = high_quality_pdb_ids[i:i + batch_size]
                placeholders = ','.join('?' for _ in batch)
                query = f'UPDATE invariants SET "2AXR" = 1 WHERE SUBSTR(chain_id, 1, 4) IN ({placeholders})'
                conn.execute(query, batch)
            conn.commit()
        print("Database update complete.")
    else:
        print("No high-quality structures found to update.")

    end_time = time.time()
    print(f"\nTotal runtime: {end_time - start_time:.2f} seconds.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape PDB metadata and filter the invariants database.")
    parser.add_argument("db_path", type=str, help="Path to the SQLite database file.")
    parser.add_argument("--reset", action="store_true", help="If set, reset the '2AXR' column to 0 and exit.")
    args = parser.parse_args()

    if args.reset:
        reset_2axr_column(args.db_path)
    else:
        run_scraper(args.db_path)