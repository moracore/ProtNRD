#!/bin/bash
#SBATCH --job-name=Schema_Adapter
#SBATCH --output=adapter_%j.log
#SBATCH --error=adapter_%j.err
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G

set -e

# --- CONFIG ---
DB_PATH="protein_geometry_invariants.db"
# REPLACE THIS with the actual path to your venv folder
VENV_PATH="3mer"

# --- SETUP ENVIRONMENT ---
# Standard venv activation
source "$VENV_PATH/bin/activate"

echo "========================================================"
echo "ADAPTING SCHEMA FOR: $DB_PATH"
echo "PYTHON: $(which python3)"
echo "========================================================"

# Use Python to execute the SQL
python3 -c "
import sqlite3
import os
import sys

db_path = '$DB_PATH'
if not os.path.exists(db_path):
    print(f'Error: Database {db_path} not found.')
    sys.exit(1)

conn = sqlite3.connect(db_path)
c = conn.cursor()

print('Cleaning up old tables...')
c.execute('DROP TABLE IF EXISTS invariants_filtered')

print('Creating invariants_filtered...')
# Note: SQLite window functions (ROW_NUMBER) require SQLite >= 3.25
sql_create = \"\"\"
CREATE TABLE invariants_filtered AS
SELECT
    chain_id,
    residue,
    length_N AS length_NA,
    length_A AS length_AC,
    length_C AS length_CN,
    angle_N,
    angle_A,
    angle_C,
    tau_NA,
    tau_AC,
    tau_CN,
    (ROW_NUMBER() OVER (PARTITION BY chain_id ORDER BY rowid) - 1) AS position
FROM invariants;
\"\"\"
try:
    c.execute(sql_create)
except sqlite3.OperationalError as e:
    print(f'SQL Error: {e}')
    print('Ensure your python environment has a recent sqlite3 version.')
    sys.exit(1)

print('Indexing...')
c.execute('CREATE INDEX IF NOT EXISTS idx_inv_filt_pos_chain ON invariants_filtered(chain_id, position)')

conn.commit()
conn.close()
print('Schema adaptation complete.')
"