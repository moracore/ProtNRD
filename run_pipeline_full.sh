#!/bin/bash
#SBATCH --job-name=full_db_pnrd
#SBATCH --output=slurm_logs/pipeline_f_%j.log
#SBATCH --error=slurm_logs/pipeline_f_%j.err
#SBATCH --time=24:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G

set -e  # Exit immediately on error

# --- CONFIGURATION ---
# IMPORTANT: Set this to the folder containing your scripts and DB
PROJECT_DIR="/users/gtn/fastscratch/3mer"
DB_PATH="proteins_v4.db"
# Path to your venv folder (assuming it's named '3mer' inside the project dir)
VENV_PATH="$PROJECT_DIR/3mer" 

# --- SETUP ENVIRONMENT ---
# 1. Go to the project directory first
cd "$PROJECT_DIR"
echo "Working Directory: $(pwd)"

# 2. Activate VENV (Replaces Conda)
echo "Activating venv at: $VENV_PATH"
source "$VENV_PATH/bin/activate"

PYTHON_CMD="python3"

echo "========================================================"
echo "STARTING ProtNRD v0.9 PIPELINE (In-Place Processing)"
echo "Target DB: $DB_PATH"
echo "========================================================"

# Step 0: Pre-Cleanup
# Drops all calculated tables to ensure a fresh run, keeping only source data.
echo "[0/4] Dropping old tables (preserving 'invariants_filtered')..."
$PYTHON_CMD -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
curs = conn.cursor()
tables_to_drop = ['3mers', 'v9_3mer_map', 'stats', 'cache_3d', 'freq']
for table in tables_to_drop:
    curs.execute(f'DROP TABLE IF EXISTS \"{table}\"')
    print(f'Dropped table: {table}')
conn.commit()
conn.execute('VACUUM') # Optional: Reclaims space before starting
conn.close()
"

# Step 1: Create the sliding window triplets table
echo "[1/4] Running Triplet Generation..."
$PYTHON_CMD step1_triplets.py "$DB_PATH"

# Step 2: Create the frequency map
echo "[2/4] Running Frequency Mapping..."
$PYTHON_CMD step2_map.py "$DB_PATH"

# Step 3: Calculate Statistics and Heatmaps
echo "[3/4] Calculating Stats & Generating Heatmaps..."
$PYTHON_CMD step3_calc.py "$DB_PATH"

# Step 4: Cleanup
echo "[4/4] Cleaning up temporary tables..."
$PYTHON_CMD -c "
import sqlite3
conn = sqlite3.connect('$DB_PATH')
conn.execute('DROP TABLE IF EXISTS \"3mers\"')
conn.execute('VACUUM')
conn.close()
"

echo "========================================================"
echo "PIPELINE COMPLETE."
echo "Final DB Size:"
du -h "$DB_PATH"
echo "========================================================"