"""
Pipeline Step 2: Cache and Stats Generation (v5.19 - Hardcoded Limits)

This script uses the pre-joined tables to generate final data products.

MAJOR REVISION (v5.19):
- Replaced all automatic limit-finding logic with a set of hardcoded,
  predefined limits for each invariant based on user specification.
- This ensures a consistent and predictable viewing window for all plots.
- Removed the now-unused `find_center_of_largest_data_cluster` function.

MAJOR REVISION (v5.18):
- Added a special-case limit for `tau_AC` (psi).
"""
import sqlite3
import time
import pandas as pd
from tqdm import tqdm
import sys
import os
import json
import multiprocessing
from itertools import combinations, product
import numpy as np

# --- Configuration ---
ANGLE_RESOLUTION = 1.0
LENGTH_RESOLUTION = 0.05
ALL_INVARIANTS = ['length_N', 'length_A', 'length_C', 'angle_N', 'angle_A', 'angle_C', 'tau_NA', 'tau_AC', 'tau_CN']
CHUNKSIZE = 500000

# --- Predefined Limits ---
FIXED_LIMITS = {
    'length_N': (1.0, 2.0),
    'length_A': (1.0, 2.0),
    'length_C': (1.0, 2.0),
    'angle_N': (0, 360),
    'angle_A': (0, 360),
    'angle_C': (0, 360),
    'tau_NA': (0, 360),
    'tau_AC': (-90, 270),
    'tau_CN': (-90, 270),
}

def calculate_and_store_limits(db_path, visual_mode=False):
    """
    Stores a fixed set of predefined limits and, if in visual mode,
    generates 1D histograms for each invariant.
    """
    plt = None
    if visual_mode:
        try:
            import matplotlib.pyplot as plt
            print("Visual mode enabled. Matplotlib imported successfully.")
            os.makedirs('limit_visuals', exist_ok=True)
            print("Plots will be saved to 'limit_visuals/' directory.")
        except ImportError:
            print("Warning: Matplotlib is not installed. Cannot generate plots for --visual mode.")
            visual_mode = False

    print("\n--- Storing predefined invariant limits ---")
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS v5_invariant_limits (
            invariant_name TEXT PRIMARY KEY, limit_min REAL, limit_max REAL
        );""")
        
        if cursor.execute("SELECT COUNT(*) FROM v5_invariant_limits").fetchone()[0] > 0:
            print("Limits table is already populated. Skipping.")
            return

        print("Limits table is empty. Storing fixed limits for all invariants...")
        limits_to_insert = []
        for inv, (limit_min, limit_max) in FIXED_LIMITS.items():
            limits_to_insert.append((inv, float(limit_min), float(limit_max)))

            if visual_mode and plt:
                df = pd.read_sql_query(f"SELECT {inv} FROM invariants_filtered WHERE {inv} IS NOT NULL;", conn)
                data = df[inv].values
                
                # Use robust modulo arithmetic to map all data into the new range
                transposed_data = limit_min + ((data - limit_min) % 360) if 'angle' in inv or 'tau' in inv else data
                
                plt.figure(figsize=(10, 6)); 
                plt.hist(transposed_data, bins=360 if 'angle' in inv or 'tau' in inv else 100, range=(limit_min, limit_max))
                plt.title(f'Distribution for {inv}'); plt.xlabel('Value'); plt.ylabel('Frequency')
                plt.xlim(limit_min, limit_max); plt.savefig(f'limit_visuals/{inv}_distribution.png'); plt.close()
        
        if visual_mode:
            print("\n" + "="*40 + "\n      Final Fixed Invariant Limits\n" + "="*40)
            print(pd.DataFrame(limits_to_insert, columns=['Invariant', 'Min Limit', 'Max Limit']).to_string(index=False))
            print("="*40 + "\n")

        cursor.executemany("INSERT OR REPLACE INTO v5_invariant_limits (invariant_name, limit_min, limit_max) VALUES (?, ?, ?)", limits_to_insert)
        conn.commit()
        print("Successfully stored all fixed invariant limits.")

def calculate_stats(df):
    """Calculates simple, global statistics for a given heatmap DataFrame."""
    matrix = df.values
    total_points = matrix.sum()
    if total_points == 0: return {'total_points': 0, 'peak_location': None, 'peak_frequency': 0}
    peak_idx = np.unravel_index(np.argmax(matrix), matrix.shape)
    peak_frequency = int(matrix[peak_idx])
    peak_location = {'x': float(df.columns[peak_idx[1]]), 'y': float(df.index[peak_idx[0]])}
    return {'total_points': int(total_points), 'peak_location': peak_location, 'peak_frequency': peak_frequency}

def process_chunk(args):
    """
    Worker function. Transposes angular data before binning using robust formula.
    """
    df_chunk, x_col, y_col, bin_size, x_lim, y_lim = args
    df_chunk.dropna(subset=[x_col, y_col], inplace=True)
    if df_chunk.empty: return {}

    # --- Use robust modulo arithmetic to map all angles into the correct range ---
    if 'angle' in x_col or 'tau' in x_col:
        x_data = df_chunk[x_col].values
        df_chunk[x_col] = x_lim['limit_min'] + ((x_data - x_lim['limit_min']) % 360)

    if 'angle' in y_col or 'tau' in y_col:
        y_data = df_chunk[y_col].values
        df_chunk[y_col] = y_lim['limit_min'] + ((y_data - y_lim['limit_min']) % 360)
    # ---------------------------------------------------------------------------

    binned_x_idx = np.floor(df_chunk[x_col] / bin_size).astype(np.int32)
    binned_y_idx = np.floor(df_chunk[y_col] / bin_size).astype(np.int32)
    return pd.Series(zip(binned_x_idx, binned_y_idx)).value_counts().to_dict()

def main():
    """Main execution function."""
    start_time = time.time()
    
    if len(sys.argv) < 2: sys.exit("Error: Please provide the database path as a command-line argument.")
    
    db_path = sys.argv[1]
    recalculate = '--recalculate' in sys.argv
    visual_mode = '--visual' in sys.argv

    if recalculate:
        print("--- RECALCULATION MODE ENABLED ---")
        with sqlite3.connect(db_path) as conn:
            print("Dropping existing cache, stats, and limits tables...")
            conn.execute("DROP TABLE IF EXISTS v5_pairwise_cache;")
            conn.execute("DROP TABLE IF EXISTS v5_pairwise_stats;")
            conn.execute("DROP TABLE IF EXISTS v5_invariant_limits;")
            conn.commit()
            print("Tables dropped.")

    calculate_and_store_limits(db_path, visual_mode=visual_mode)
    
    with sqlite3.connect(db_path) as conn:
        print("\n--- Starting Heatmap Cache Generation ---")
        conn.execute("CREATE TABLE IF NOT EXISTS v5_pairwise_cache (plot_key TEXT PRIMARY KEY, heatmap_data JSON);")
        conn.execute("CREATE TABLE IF NOT EXISTS v5_pairwise_stats (plot_key TEXT PRIMARY KEY, stats_data JSON);")
        completed_jobs = set(pd.read_sql_query("SELECT plot_key FROM v5_pairwise_cache", conn)['plot_key'])
        print(f"Found {len(completed_jobs)} already completed jobs to skip.")
        
        print("Fetching invariant limits from database...")
        limits_df = pd.read_sql_query("SELECT * FROM v5_invariant_limits", conn)
        limits = limits_df.set_index('invariant_name').to_dict('index')

    all_possible_jobs = []
    order = {'length': 0, 'angle': 1, 'tau': 2}
    for inv1, inv2 in combinations(ALL_INVARIANTS, 2):
        res = LENGTH_RESOLUTION if 'length' in inv1 or 'length' in inv2 else ANGLE_RESOLUTION
        key_inv1, key_inv2 = sorted([inv1, inv2], key=lambda i: (order.get(''.join(filter(str.isalpha, i)), 99), ALL_INVARIANTS.index(i)))
        key = f"{key_inv1}_vs_{key_inv2}_Any_Any_bin{res}"
        all_possible_jobs.append((key, res, 'invariants_filtered', inv1, inv2))

    for offset in range(1, 5):
        table_name = {1: 'v5_pairwise', 2: 'v5_triplets', 3: 'v5_quads', 4: 'v5_quints'}[offset]
        for inv1, inv2 in product(ALL_INVARIANTS, repeat=2):
            res = LENGTH_RESOLUTION if 'length' in inv1 or 'length' in inv2 else ANGLE_RESOLUTION
            x_col, y_col = f"{inv1}_1", f"{inv2}_{offset+1}"
            key = f"{inv1}_vs_{inv2}+{offset}_Any_Any_bin{res}"
            all_possible_jobs.append((key, res, table_name, x_col, y_col))
    
    jobs_to_run = [job for job in all_possible_jobs if job[0] not in completed_jobs]
    
    if not jobs_to_run:
        print("All jobs have already been completed. Nothing to do.")
        sys.exit(0)

    print(f"Total jobs to process: {len(jobs_to_run)} (out of {len(all_possible_jobs)} total)")
    num_processes = int(os.environ.get('SLURM_CPUS_PER_TASK', os.cpu_count() or 1))
    print(f"Starting processing with {num_processes} worker(s)...")

    plots_to_insert, stats_to_insert, error_logs = [], [], []

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=120)
    with multiprocessing.Pool(processes=num_processes) as pool:
        for job_args in tqdm(jobs_to_run, desc="Overall Progress"):
            job_key, bin_size, table_name, x_col, y_col = job_args
            try:
                base_inv1 = x_col if table_name == 'invariants_filtered' else '_'.join(x_col.split('_')[:-1])
                base_inv2 = y_col if table_name == 'invariants_filtered' else '_'.join(y_col.split('_')[:-1])
                x_lim = limits.get(base_inv1)
                y_lim = limits.get(base_inv2)

                final_counts = {}
                sql_query = f"SELECT {x_col}, {y_col} FROM {table_name}"
                chunk_iterator = pd.read_sql_query(sql_query, conn, chunksize=CHUNKSIZE)
                worker_args = [(chunk, x_col, y_col, bin_size, x_lim, y_lim) for chunk in chunk_iterator]
                partial_counts_list = pool.map(process_chunk, worker_args)
                
                for partial_counts in partial_counts_list:
                    for key, value in partial_counts.items():
                        final_counts[key] = final_counts.get(key, 0) + value

                if not final_counts: continue

                min_x_idx = int(np.floor(x_lim['limit_min'] / bin_size)); max_x_idx = int(np.ceil(x_lim['limit_max'] / bin_size))
                min_y_idx = int(np.floor(y_lim['limit_min'] / bin_size)); max_y_idx = int(np.ceil(y_lim['limit_max'] / bin_size))
                x_int_grid, y_int_grid = np.arange(min_x_idx, max_x_idx + 1), np.arange(min_y_idx, max_y_idx + 1)
                
                heatmap_int_df = pd.DataFrame(0, index=y_int_grid, columns=x_int_grid, dtype=np.int32)

                for (x_idx, y_idx), count in final_counts.items():
                    if x_idx in x_int_grid and y_idx in y_int_grid:
                        heatmap_int_df.loc[y_idx, x_idx] = count
                
                heatmap_full = heatmap_int_df.copy()
                heatmap_full.index, heatmap_full.columns = heatmap_full.index * bin_size, heatmap_full.columns * bin_size
                
                plot_data = {'x': [float(c) for c in heatmap_full.columns], 'y': [float(i) for i in heatmap_full.index], 'z': heatmap_full.values.tolist()}
                stats_data = calculate_stats(heatmap_full)
                
                plots_to_insert.append((job_key, json.dumps(plot_data))); stats_to_insert.append((job_key, json.dumps(stats_data)))
            except Exception as e:
                error_logs.append((job_key, e))
    conn.close()

    if plots_to_insert:
        print(f"\nFinished processing. Inserting {len(plots_to_insert)} new results into the database...")
        with sqlite3.connect(db_path, timeout=300) as conn_write:
            conn_write.executemany("INSERT OR REPLACE INTO v5_pairwise_cache (plot_key, heatmap_data) VALUES (?, ?)", plots_to_insert)
            conn_write.executemany("INSERT OR REPLACE INTO v5_pairwise_stats (plot_key, stats_data) VALUES (?, ?)", stats_to_insert)
            conn_write.commit()
        print("Database insertion complete.")

    if error_logs:
        print("\n--- Errors Encountered ---")
        for key, err in error_logs:
            print(f"Job '{key}': {type(err).__name__} - {err}")

    end_time = time.time()
    print(f"Total script runtime: {end_time - start_time:.2f}s.")

if __name__ == "__main__":
    main()

