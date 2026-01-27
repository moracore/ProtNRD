import pandas as pd
import numpy as np
import sys
import os
import sqlite3

# Import your custom tools
from tools.pipeline_constants import THR_FREQUENCY
from tools.stats_utils import calculate_2d_torsion_stats, calculate_circular_stats, calculate_linear_stats
from tools.heatmap_utils import generate_sparse_heatmap
from tools.database_utils import get_connection, initialize_v9_tables, batch_insert_v9_stats, insert_heatmap

# Define the pairs we want to cache 3D heatmaps for
HEATMAP_PAIRS = [
    ('tau_NA_2', 'tau_AC_2', 'phi_psi'),    # Standard Ramachandran
    ('tau_NA_2', 'tau_CN_2', 'phi_omega'),  # Phi vs Omega
    ('tau_AC_2', 'tau_CN_2', 'psi_omega')   # Psi vs Omega
]

def main(db_path):
    if not os.path.exists(db_path):
        print(f"Creating new database at {db_path}...")

    # Connect with high timeout for Slurm/shared environments
    conn = get_connection(db_path)
    
    # 1. Setup the 79-column schema (Warning: This drops existing tables!)
    print("--- Initializing v0.9 Comprehensive Schema ---")
    initialize_v9_tables(conn)

    # 2. Fetch target 3-mers
    print("Fetching 3-mer list from 'freq' table...")
    try:
        targets = pd.read_sql_query("SELECT * FROM freq", conn)
    except Exception as e:
        sys.exit(f"Error reading 'freq' table. Ensure the DB is populated with raw data first: {e}")

    total_targets = len(targets)
    print(f"Total 3-mers to process: {total_targets}")

    stats_entries = []
    
    # 3. Process each 3-mer
    for idx, row in targets.iterrows():
        t_name = row['3mer']
        res_1, res_2, res_3 = row['res_1'], row['res_2'], row['res_3']
        
        if idx % 100 == 0:
            print(f"[{idx}/{total_targets}] Processing: {t_name}")

        # Fetch full geometry
        query = "SELECT * FROM '3mers' WHERE res_1=? AND res_2=? AND res_3=?"
        df = pd.read_sql_query(query, conn, params=(res_1, res_2, res_3))

        if df.empty:
            continue

        # --- A. CALCULATE STATS ---
        # 1. Global 2D Stats (Phi-Psi is the reference for the stats table)
        g2d = calculate_2d_torsion_stats(df['tau_NA_2'].values, df['tau_AC_2'].values)
        
        # 2. Torsions
        phi_s = calculate_circular_stats(df['tau_NA_2'].values)
        psi_s = calculate_circular_stats(df['tau_AC_2'].values)
        omg_s = calculate_circular_stats(df['tau_CN_2'].values)

        # 3. Lengths
        l_na = calculate_linear_stats(df['length_NA_2'].values, window=0.02)
        l_ac = calculate_linear_stats(df['length_AC_2'].values, window=0.02)
        l_cn = calculate_linear_stats(df['length_CN_2'].values, window=0.02)

        # 4. Bond Angles
        a_n = calculate_linear_stats(df['angle_N_2'].values, window=5.0)
        a_a = calculate_linear_stats(df['angle_A_2'].values, window=5.0)
        a_c = calculate_linear_stats(df['angle_C_2'].values, window=5.0)

        # Convert numpy types to python native types to avoid BLOB storage
        entry = (
            t_name, int(row['frequency']),
            *[float(x) if x is not None else None for x in g2d],
            *[float(x) if x is not None else None for x in phi_s],
            *[float(x) if x is not None else None for x in psi_s],
            *[float(x) if x is not None else None for x in omg_s],
            *[float(x) if x is not None else None for x in l_na],
            *[float(x) if x is not None else None for x in l_ac],
            *[float(x) if x is not None else None for x in l_cn],
            *[float(x) if x is not None else None for x in a_n],
            *[float(x) if x is not None else None for x in a_a],
            *[float(x) if x is not None else None for x in a_c]
        )
        stats_entries.append(entry)

        # --- B. GENERATE HEATMAP CACHE (The Fix) ---
        if row['frequency'] >= THR_FREQUENCY:
            # Loop through the defined pairs to generate multiple plots per 3-mer
            for col_x, col_y, suffix in HEATMAP_PAIRS:
                try:
                    heatmap_json = generate_sparse_heatmap(df, col_x, col_y)
                    plot_key = f"{t_name}_{suffix}"
                    insert_heatmap(conn, plot_key, heatmap_json)
                except Exception as e:
                    print(f"Skipping plot {t_name}_{suffix}: {e}")

        # Batch insert
        if len(stats_entries) >= 500:
            batch_insert_v9_stats(conn, stats_entries)
            stats_entries = []

    # Final commit
    if stats_entries:
        batch_insert_v9_stats(conn, stats_entries)
    
    conn.close()
    print("Pipeline Step 3 Complete: Full 79-metric cache + Multi-pair 3D Cache ready.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python 3_3M_cache.py <db_path>")
    else:
        main(sys.argv[1])