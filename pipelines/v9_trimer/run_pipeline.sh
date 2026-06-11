#!/bin/bash
set -e
# Trimer (v9) pipeline. Operates in-place on a SQLite DB that already contains
# the `invariants_filtered` table (chain_id, position, residue, tau_*, length_*,
# angle_*). Produces: '3mers' (intermediate), v9_3mer_map, stats, cache_3d.
#
# Run from this directory so `tools` is importable:
#   cd pipelines/v9_trimer && ./run_pipeline.sh /path/to/proteins_v9.db

DB_PATH="${1:?Usage: ./run_pipeline.sh <db_path>}"
PY="${PYTHON_CMD:-python3}"

echo "[1/3] Flattening triplets (position-based join)..."
$PY 1_3M_flat.py "$DB_PATH"

echo "[2/3] Building frequency map (v9_3mer_map)..."
$PY 2_3M_freq.py "$DB_PATH"

echo "[3/3] Position-aware stats + integer-binned p1/p2/p3 heatmaps..."
$PY 3_3M_cache.py "$DB_PATH"

echo "Done."
