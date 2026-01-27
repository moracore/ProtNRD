"""
Pipeline Step 2: Main Cache & Stats Generation (v7.2 - Unified Stats)

This script orchestrates the entire backend pipeline. It is responsible for:
1.  Generating the *correct* list of all 178,416 required data products,
    categorized by their type (3D_VIZ, STATS_AND_HISTO, STATS_ONLY).
2.  Managing a parallel multiprocessing pool to process these jobs.
3.  Importing modular functions from the 'tools/' directory to perform
    the specific calculations.
4.  Saving all results to THREE final 'v7_...' database tables based
    on the required output type.

This script is resumable. Use --recalculate to force-drop all cache tables.
"""
import sqlite3
import time
import pandas as pd
from tqdm import tqdm
import sys
import os
import json
import multiprocessing
from itertools import product
import argparse

# Import the modular tools from the 'tools' subdirectory
from tools.pipeline_utils import get_db_connection, get_invariant_limits
# UPDATED: Renamed import
from tools.generate_visualizations import generate_visualization_data

# Import configuration from the new constants file
from tools.pipeline_constants import (
    RESOLUTION_LEVELS, RESIDUE_CONTEXTS, ALL_INVARIANTS,
    TORSION_INVARIANTS, NON_TORSION_INVARIANTS
)

# --- Database Schemas (v7.2 - Unified Stats) ---

SCHEMA_V7_3D_CACHE = """
CREATE TABLE IF NOT EXISTS v7_3D_cache (
    plot_key TEXT PRIMARY KEY,
    data JSON NOT NULL
);
"""

SCHEMA_V7_HISTO_CACHE = """
CREATE TABLE IF NOT EXISTS v7_histo_cache (
    plot_key TEXT NOT NULL,
    axis TEXT NOT NULL,
    data JSON NOT NULL,
    PRIMARY KEY (plot_key, axis)
);
"""

# UPDATED: New unified stats schema
SCHEMA_V7_STATS = """
CREATE TABLE IF NOT EXISTS v7_stats (
    plot_key TEXT PRIMARY KEY,
    job_type TEXT NOT NULL,
    population INTEGER,
    
    -- Raw 1D Stats (X-Axis)
    mean_x REAL,
    variance_x REAL,
    median_x REAL,
    min_x REAL,
    max_x REAL,
    freq_at_mean_x INTEGER,
    
    -- Raw 1D Stats (Y-Axis)
    mean_y REAL,
    variance_y REAL,
    median_y REAL,
    min_y REAL,
    max_y REAL,
    freq_at_mean_y INTEGER,
    
    -- Raw 2D Stats
    covariance REAL,
    
    -- Binned 2D Stats (from Heatmap)
    peak_x REAL,
    peak_y REAL,
    peak_freq INTEGER
);
"""

def get_existing_keys(conn):
    """Gets all plot_keys from the primary stats table to allow for resumability."""
    try:
        # Check v7_stats, as it's the primary indicator of a completed job
        df = pd.read_sql_query(f"SELECT plot_key FROM v7_stats", conn)
        return set(df['plot_key'])
    except pd.io.sql.DatabaseError:
        return set()

def drop_tables(conn):
    """Drops all cache and stats tables for a full recalculation."""
    print("WARNING: --recalculate flag set. Dropping cache and stats tables...")
    conn.execute("DROP TABLE IF EXISTS v7_3D_cache;")
    conn.execute("DROP TABLE IF EXISTS v7_histo_cache;")
    conn.execute("DROP TABLE IF EXISTS v7_stats;")
    # Drop old v6 tables
    print("Dropping old v6 tables...")
    conn.execute("DROP TABLE IF EXISTS v6_3D_cache;")
    conn.execute("DROP TABLE IF EXISTS v6_histo_cache;")
    conn.execute("DROP TABLE IF EXISTS v6_stats;")
    print("Tables dropped.")


def process_job(job_args):
    """
    Worker function. Receives one job tuple and calls the 
    visualization tool to generate heatmap, unified stats, and 1D histograms.
    
    Returns a tuple: 
    (job_key, job_type, cache_data, stats_data_tuple, histo_data_x, histo_data_y)
    """
    # Unpack all arguments
    db_path, plot_key, job_type, inv1, offset, res1, inv2, res2, res_level = job_args
    
    effective_res_level = res_level if res_level else RESOLUTION_LEVELS[0]

    try:
        # UPDATED: Renamed function call
        heatmap_data, stats_dict, histo_data_x, histo_data_y = generate_visualization_data(
            db_path, inv1, inv2, offset, res1, res2, effective_res_level,
            TORSION_INVARIANTS
        )
        
        # UPDATED: Format stats tuple for the new 19-column v7_stats table
        formatted_stats = (
            plot_key,
            job_type,
            stats_dict.get('population'),
            stats_dict.get('mean_x'),
            stats_dict.get('variance_x'),
            stats_dict.get('median_x'),
            stats_dict.get('min_x'),
            stats_dict.get('max_x'),
            stats_dict.get('freq_at_mean_x'),
            stats_dict.get('mean_y'),
            stats_dict.get('variance_y'),
            stats_dict.get('median_y'),
            stats_dict.get('min_y'),
            stats_dict.get('max_y'),
            stats_dict.get('freq_at_mean_y'),
            stats_dict.get('covariance'),
            stats_dict.get('peak_x'),
            stats_dict.get('peak_y'),
            stats_dict.get('peak_freq')
        )
            
        # Return all items for the main loop to process
        return (
            plot_key, 
            job_type, 
            json.dumps(heatmap_data), 
            formatted_stats, 
            json.dumps(histo_data_x) if histo_data_x else None,
            json.dumps(histo_data_y) if histo_data_y else None
        )

    except Exception as e:
        # Return a tuple that matches the others, with error info
        return plot_key, "ERROR", None, (f"{type(e).__name__} - {e}",), None, None


def _write_batch_to_db(conn, results_3d_cache, results_1d_histo_cache, results_stats):
    """Helper function to write batches to the database in a transaction."""
    try:
        cursor = conn.cursor()
        
        if results_3d_cache:
            cursor.executemany("INSERT OR REPLACE INTO v7_3D_cache (plot_key, data) VALUES (?, ?)", results_3d_cache)
        
        if results_1d_histo_cache:
            cursor.executemany("INSERT OR REPLACE INTO v7_histo_cache (plot_key, axis, data) VALUES (?, ?, ?)", results_1d_histo_cache)
        
        if results_stats:
            # UPDATED: New INSERT statement with 19 columns
            cursor.executemany("""
                INSERT OR REPLACE INTO v7_stats 
                (plot_key, job_type, population, 
                 mean_x, variance_x, median_x, min_x, max_x, freq_at_mean_x,
                 mean_y, variance_y, median_y, min_y, max_y, freq_at_mean_y,
                 covariance, peak_x, peak_y, peak_freq) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, results_stats)
        
        conn.commit()
    except Exception as e:
        print(f"--- DATABASE BATCH WRITE FAILED: {e} ---")
        conn.rollback()

def main(db_path, recalculate=False):
    start_time = time.time()
    
    limits = get_invariant_limits()
    print(f"Loaded {len(limits)} invariant limits.")

    with get_db_connection(db_path, read_only=False) as conn:
        if recalculate:
            drop_tables(conn)
            
        print("Ensuring cache and stats tables exist...")
        conn.execute(SCHEMA_V7_3D_CACHE)
        conn.execute(SCHEMA_V7_HISTO_CACHE)
        conn.execute(SCHEMA_V7_STATS)
        
        completed_jobs = get_existing_keys(conn)
        print(f"Found {len(completed_jobs)} previously completed jobs.")
    
    jobs_to_run = []
    
    # --- START: CORRECTED JOB GENERATION LOGIC ---
    print("Generating jobs based on categorization rules...")
    
    all_inv_pairs = list(product(ALL_INVARIANTS, ALL_INVARIANTS)) # 81 pairs
    all_res_pairs = list(product(RESIDUE_CONTEXTS, RESIDUE_CONTEXTS)) # 441 pairs
    all_offsets = range(5) # 5 offsets
    
    total_combinations = len(all_inv_pairs) * len(all_res_pairs) * len(all_offsets)
    print(f"Checking {total_combinations} (9x9x21x21x5) total combinations...")

    count_3d_viz = 0
    count_stats_histo = 0
    count_stats_only = 0
    count_excluded = 0
    
    pbar = tqdm(total=total_combinations)
    for (inv1, inv2) in all_inv_pairs:
        for (res1, res2) in all_res_pairs:
            for offset in all_offsets:
                pbar.update(1)

                # 2. Apply the exclusion rule (the 189 cases)
                if (inv1 == inv2) and (offset == 0) and (res1 == res2):
                    count_excluded += 1
                    continue # Skip this job

                # 3. Apply the categorization rules
                is_any_any = (res1 == "Any" and res2 == "Any")
                is_torsion_torsion = (inv1 in TORSION_INVARIANTS and inv2 in TORSION_INVARIANTS)
                is_other_other = (inv1 in NON_TORSION_INVARIANTS and inv2 in NON_TORSION_INVARIANTS)
                is_torsion_other = not is_torsion_torsion and not is_other_other
                
                job_key_base = f"{inv1}_vs_{inv2}+{offset}_{res1}_{res2}"
                
                # --- Rule 1 & 2: 3D Visualizations ---
                if is_any_any or is_torsion_torsion:
                    job_type = "3D_VIZ"
                    for res_level in RESOLUTION_LEVELS:
                        plot_key = f"{job_key_base}_{res_level}"
                        if plot_key not in completed_jobs:
                            jobs_to_run.append((db_path, plot_key, job_type, inv1, offset, res1, inv2, res2, res_level))
                        count_3d_viz += 1
                
                # --- Rule 4: Torsion vs Other (Stats + 2D Histo) ---
                elif is_torsion_other:
                    job_type = "STATS_AND_HISTO"
                    plot_key = job_key_base # No res_level in key
                    if plot_key not in completed_jobs:
                        jobs_to_run.append((db_path, plot_key, job_type, inv1, offset, res1, inv2, res2, None))
                    count_stats_histo += 1

                # --- Rule 3: Other vs Other (Stats Table Only) ---
                elif is_other_other:
                    job_type = "STATS_ONLY"
                    plot_key = job_key_base # No res_level in key
                    if plot_key not in completed_jobs:
                        jobs_to_run.append((db_path, plot_key, job_type, inv1, offset, res1, inv2, res2, None))
                    count_stats_only += 1
    
    pbar.close()
    
    print("--- Job Generation Summary ---")
    print(f"Total Excluded (Offset 0, Self-Pair, Same-Res): {count_excluded}")
    print(f"3D Visualization Jobs (per-res level): {count_3d_viz}")
    print(f"Stats + 1D Histo Jobs: {count_stats_histo}")
    print(f"Stats Only Jobs: {count_stats_only}")
    total_outputs = count_3d_viz + count_stats_histo + count_stats_only
    print(f"Total required outputs: {total_outputs}")
    print(f"Sanity Check: {count_3d_viz/len(RESOLUTION_LEVELS) + count_stats_histo + count_stats_only} base pairs = 178,416")
    # --- END: CORRECTED JOB GENERATION LOGIC ---


    if not jobs_to_run:
        print("All required jobs are already complete. Nothing to do.")
        sys.exit(0)

    print(f"Total new jobs to process: {len(jobs_to_run)}")
    num_processes = int(os.environ.get('SLURM_CPUS_PER_TASK', 16))
    print(f"Starting processing with {num_processes} worker(s)...")
    
    BATCH_SIZE = 1000 
    
    with get_db_connection(db_path, read_only=False, timeout=600) as conn:
        with multiprocessing.Pool(processes=num_processes) as pool:
            
            results_3d_cache = []
            results_1d_histo_cache = []
            results_stats = []
            error_logs = []
            
            job_iterator = pool.imap_unordered(process_job, jobs_to_run)
            
            for i, result in enumerate(tqdm(job_iterator, total=len(jobs_to_run))):
                job_key, job_type, cache_data, stats_data_tuple, histo_data_x, histo_data_y = result
                
                if job_type == 'ERROR':
                    error_logs.append(f"{job_key} -> {stats_data_tuple[0]}")
                    continue
                
                # stats_data_tuple[2] is 'population'
                if not (stats_data_tuple and stats_data_tuple[2] is not None and stats_data_tuple[2] > 0):
                    error_logs.append(f"{job_key} -> Population is 0 or stats are None")
                    continue
                
                # --- START: CORRECTED BATCH WRITE LOGIC ---
                # Always save stats
                results_stats.append(stats_data_tuple)

                if job_type == "3D_VIZ":
                    results_3d_cache.append((job_key, cache_data))
                    if histo_data_x:
                        results_1d_histo_cache.append((job_key, 'x', histo_data_x))
                    if histo_data_y:
                        results_1d_histo_cache.append((job_key, 'y', histo_data_y))
                
                elif job_type == "STATS_AND_HISTO":
                    if histo_data_x:
                        results_1d_histo_cache.append((job_key, 'x', histo_data_x))
                    if histo_data_y:
                        results_1d_histo_cache.append((job_key, 'y', histo_data_y))
                
                elif job_type == "STATS_ONLY":
                    pass # Stats are already added
                # --- END: CORRECTED BATCH WRITE LOGIC ---

                if (i + 1) % BATCH_SIZE == 0:
                    _write_batch_to_db(conn, results_3d_cache, results_1d_histo_cache, results_stats)
                    results_3d_cache.clear()
                    results_1d_histo_cache.clear()
                    results_stats.clear()
            
            # Write final batch
            print("\nWriting final batch...")
            _write_batch_to_db(conn, results_3d_cache, results_1d_histo_cache, results_stats)

    
    if error_logs: 
        print(f"\n--- {len(error_logs)} Errors Encountered (or empty data sets) ---")
        for e in error_logs[:20]: print(e)
        if len(error_logs) > 20: print(f"...and {len(error_logs)-20} more.")

    end_time = time.time()
    print(f"Database insertion complete. Total script runtime: {time.time() - start_time:.2f}s.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the v7.2 (Unified Stats) data caching pipeline.")
    parser.add_argument("db_path", type=str, help="Path to the SQLite database.")
    parser.add_argument("--recalculate", action="store_true", help="Drop and recalculate all cache and stats tables.")
    args = parser.parse_args()
    
    main(args.db_path, args.recalculate)