#!/bin/bash
#SBATCH --job-name=Clean-Up
#SBATCH --output=cleanup_%j.log
#SBATCH --error=cleanup_%j.err
#SBATCH --time=01:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G

set -e

# --- CONFIG ---
DB_PATH="app/proteins_v4.db"
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
c.execute('DROP TABLE IF EXISTS invariants')
c.execute('.VACUUM')
print('clean-up complete.')
"