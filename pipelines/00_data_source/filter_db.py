"""
Creates two filtered databases from the source invariants DB.

2A: uses '2AXR' column set by original_scraper.py (X-ray, resolution <= 2.0 A)
3A: uses pdb_resolution table (X-ray, resolution < 3.0 A)

Each output DB contains a single `invariants_filtered` table with:
  - Renamed/NULLed bond columns (0.0 terminal artifacts -> NULL)
  - Sequential `position` per chain (via ROW_NUMBER)
"""

import sqlite3
import shutil
import sys
import os
import time


CREATE_FILTERED_2A = """
CREATE TABLE invariants_filtered AS
SELECT
    i.chain_id,
    i.residue,
    NULLIF(i.length_N, 0.0) AS length_CN,
    NULLIF(i.length_A, 0.0) AS length_NA,
    NULLIF(i.length_C, 0.0) AS length_AC,
    NULLIF(i.angle_N,  0.0) AS angle_N,
    NULLIF(i.angle_A,  0.0) AS angle_A,
    NULLIF(i.angle_C,  0.0) AS angle_C,
    NULLIF(i.tau_NA,   0.0) AS tau_NA,
    NULLIF(i.tau_AC,   0.0) AS tau_AC,
    NULLIF(i.tau_CN,   0.0) AS tau_CN,
    (ROW_NUMBER() OVER (PARTITION BY i.chain_id ORDER BY i.rowid) - 1) AS position
FROM invariants i
WHERE i."2AXR" = 1;
"""

CREATE_FILTERED_3A = """
CREATE TABLE invariants_filtered AS
SELECT
    i.chain_id,
    i.residue,
    NULLIF(i.length_N, 0.0) AS length_CN,
    NULLIF(i.length_A, 0.0) AS length_NA,
    NULLIF(i.length_C, 0.0) AS length_AC,
    NULLIF(i.angle_N,  0.0) AS angle_N,
    NULLIF(i.angle_A,  0.0) AS angle_A,
    NULLIF(i.angle_C,  0.0) AS angle_C,
    NULLIF(i.tau_NA,   0.0) AS tau_NA,
    NULLIF(i.tau_AC,   0.0) AS tau_AC,
    NULLIF(i.tau_CN,   0.0) AS tau_CN,
    (ROW_NUMBER() OVER (PARTITION BY i.chain_id ORDER BY i.rowid) - 1) AS position
FROM invariants i
JOIN pdb_resolution r
  ON upper(substr(i.chain_id, 1, instr(i.chain_id, '-') - 1)) = r.pdb_id
WHERE r.is_xray = 1
  AND r.resolution IS NOT NULL
  AND r.resolution < 3.0;
"""

FILTER_CONFIGS = [
    {'suffix': '2A', 'label': 'X-ray, resolution <= 2.0 A (2AXR column)', 'sql': CREATE_FILTERED_2A},
    {'suffix': '3A', 'label': 'X-ray, resolution < 3.0 A (pdb_resolution)', 'sql': CREATE_FILTERED_3A},
]


def build_filtered_db(src_path: str, out_path: str, cfg: dict):
    label = cfg['label']
    if os.path.exists(out_path):
        print(f"  Removing existing {out_path}...")
        os.remove(out_path)

    print(f"  Copying source DB to {out_path}...")
    shutil.copy2(src_path, out_path)

    print(f"  Building invariants_filtered ({label})...")
    with sqlite3.connect(out_path, timeout=7200) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("DROP TABLE IF EXISTS invariants_filtered;")
        conn.execute(cfg['sql'])

        print("  Indexing...")
        conn.execute(
            "CREATE INDEX idx_inv_filt_chain_pos "
            "ON invariants_filtered(chain_id, position);"
        )
        conn.commit()

        n = conn.execute("SELECT COUNT(*) FROM invariants_filtered").fetchone()[0]
        chains = conn.execute(
            "SELECT COUNT(DISTINCT chain_id) FROM invariants_filtered"
        ).fetchone()[0]

        print("  Dropping raw tables from output DB...")
        conn.execute("DROP TABLE IF EXISTS invariants;")
        conn.execute("DROP TABLE IF EXISTS pdb_resolution;")
        conn.execute("VACUUM;")
        conn.commit()

    print(f"  -> {n:,} residues across {chains:,} chains.")


def main(db_path: str):
    if not os.path.exists(db_path):
        sys.exit(f"Error: {db_path} not found.")

    with sqlite3.connect(db_path) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        cols = {r[1] for r in conn.execute("PRAGMA table_info(invariants)")}
        if '"2AXR"' not in cols and '2AXR' not in cols:
            sys.exit("Error: '2AXR' column missing from invariants. Run original_scraper.py first.")
        if 'pdb_resolution' not in tables:
            sys.exit("Error: 'pdb_resolution' table missing. Run add_resolution_flags.py first.")

    base_dir = os.path.dirname(os.path.abspath(db_path))
    t0 = time.time()

    for cfg in FILTER_CONFIGS:
        out_path = os.path.join(base_dir, f"protein_geometry_{cfg['suffix']}.db")
        print(f"\n=== Building {os.path.basename(out_path)} ===")
        build_filtered_db(db_path, out_path, cfg)

    print(f"\nAll done in {time.time()-t0:.0f}s.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python filter_db.py <db_path>")
    main(sys.argv[1])