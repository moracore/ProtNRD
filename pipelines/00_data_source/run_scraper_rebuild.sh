#!/bin/bash
#SBATCH --job-name=scraper_rebuild
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=72:00:00
#SBATCH --output=/users/gtn/fastscratch/3mer/slurm_logs/%j_scraper_rebuild.out
#SBATCH --error=/users/gtn/fastscratch/3mer/slurm_logs/%j_scraper_rebuild.err

set -eo pipefail

SCRIPT_DIR="/users/gtn/fastscratch/3mer"
SRC_DB="${SCRIPT_DIR}/protein_geometry_invariants.db"
PY="/mnt/fastscratch/users/gtn/jack/jack_env/bin/python3"

echo "=== Step 1: Run resumable scraper (sets 2AXR on source DB) ==="
echo "  Resumes from last checkpoint if restarted."
$PY "${SCRIPT_DIR}/resumable_scraper.py" "$SRC_DB"

echo ""
echo "=== Step 2: Rebuild protein_geometry_2A.db and protein_geometry_3A.db from scratch ==="
$PY "${SCRIPT_DIR}/filter_db.py" "$SRC_DB"

echo ""
echo "=== Done ==="