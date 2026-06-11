#!/bin/bash
# Run this AFTER fix_resolution.sh has completed and you're happy with the preview counts.
set -eo pipefail

SCRIPT_DIR="/users/gtn/fastscratch/3mer"
SRC_DB="${SCRIPT_DIR}/protein_geometry_invariants.db"
DB_2A="${SCRIPT_DIR}/protein_geometry_2A.db"
DB_3A="${SCRIPT_DIR}/protein_geometry_3A.db"
PY="/mnt/fastscratch/users/gtn/jack/jack_env/bin/python3"

$PY - <<EOF
import sqlite3

src = sqlite3.connect("${SRC_DB}")
valid_2a = {r[0] for r in src.execute(
    "SELECT pdb_id FROM pdb_resolution WHERE is_xray=1 AND resolution IS NOT NULL AND resolution<=2.0"
)}
valid_3a = {r[0] for r in src.execute(
    "SELECT pdb_id FROM pdb_resolution WHERE is_xray=1 AND resolution IS NOT NULL AND resolution<3.0"
)}
src.close()

for db_path, valid, label in [
    ("${DB_2A}", valid_2a, "2A"),
    ("${DB_3A}", valid_3a, "3A"),
]:
    print(f"\n=== Applying to {label} DB ===")
    conn = sqlite3.connect(db_path, timeout=3600)
    conn.execute("PRAGMA journal_mode=WAL;")
    bad_chains = [r[0] for r in conn.execute("SELECT DISTINCT chain_id FROM invariants_filtered")
                  if r[0][:4].upper() not in valid]
    print(f"Chains to remove: {len(bad_chains)}")
    for i in range(0, len(bad_chains), 500):
        batch = bad_chains[i:i+500]
        conn.execute(f"DELETE FROM invariants_filtered WHERE chain_id IN ({','.join('?'*len(batch))})", batch)
    conn.commit()
    n, c = conn.execute("SELECT COUNT(*), COUNT(DISTINCT chain_id) FROM invariants_filtered").fetchone()
    print(f"Remaining: {n:,} residues, {c:,} chains")
    print("Vacuuming...")
    conn.execute("VACUUM;")
    conn.close()

print("\nDone. Re-run pipelines to rebuild app DB.")
EOF