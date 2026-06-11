#!/bin/bash
#SBATCH --job-name=fix_resolution
#SBATCH --cpus-per-task=16
#SBATCH --mem=16G
#SBATCH --time=12:00:00
#SBATCH --output=/users/gtn/fastscratch/3mer/slurm_logs/%j_fix_res.out
#SBATCH --error=/users/gtn/fastscratch/3mer/slurm_logs/%j_fix_res.err

set -eo pipefail

SCRIPT_DIR="/users/gtn/fastscratch/3mer"
SRC_DB="${SCRIPT_DIR}/protein_geometry_invariants.db"
DB_2A="${SCRIPT_DIR}/protein_geometry_2A.db"
DB_3A="${SCRIPT_DIR}/protein_geometry_3A.db"
PY="/mnt/fastscratch/users/gtn/jack/jack_env/bin/python3"

echo "=== Step 1: Wipe pdb_resolution and re-fetch from CIF files ==="
$PY - <<EOF
import sqlite3
conn = sqlite3.connect("${SRC_DB}")
before = conn.execute("SELECT COUNT(*) FROM pdb_resolution WHERE is_xray=1 AND resolution<=2.0").fetchone()[0]
print(f"PDB IDs passing 2A filter BEFORE re-fetch: {before}")
conn.execute("DELETE FROM pdb_resolution;")
conn.commit()
conn.close()
print("pdb_resolution cleared.")
EOF

echo ""
echo "=== Step 2: Re-fetch using CIF files (exact original method) ==="
$PY "${SCRIPT_DIR}/add_resolution_flags.py" "$SRC_DB"

echo ""
echo "=== Step 3: Preview — how many residues would remain? ==="
$PY - <<EOF
import sqlite3
src  = sqlite3.connect("${SRC_DB}")
db2a = sqlite3.connect("${DB_2A}")

valid = {r[0] for r in src.execute(
    "SELECT pdb_id FROM pdb_resolution WHERE is_xray=1 AND resolution IS NOT NULL AND resolution<=2.0"
)}
after = src.execute("SELECT COUNT(*) FROM pdb_resolution WHERE is_xray=1 AND resolution<=2.0").fetchone()[0]
print(f"PDB IDs passing 2A filter AFTER re-fetch: {after}")

total, keep, remove = 0, 0, 0
for (chain_id,) in db2a.execute("SELECT DISTINCT chain_id FROM invariants_filtered"):
    pdb = chain_id[:4].upper()
    n = db2a.execute("SELECT COUNT(*) FROM invariants_filtered WHERE chain_id=?", (chain_id,)).fetchone()[0]
    total += n
    if pdb in valid:
        keep += n
    else:
        remove += n

chains_keep = db2a.execute("""
    SELECT COUNT(DISTINCT chain_id) FROM invariants_filtered
    WHERE upper(substr(chain_id,1,4)) IN ({})
""".format(','.join('?'*len(valid))), list(valid)).fetchone()[0]

print(f"Would remain:  {keep:,} residues, {chains_keep:,} chains")
print(f"Would remove:  {remove:,} residues")
print(f"Target:        10,797,995 residues")

src.close()
db2a.close()
EOF

echo ""
echo "=== Preview complete. To apply, run: bash ${SCRIPT_DIR}/apply_resolution_fix.sh ==="