## Pipeline Step 2 (v0.8): Main Cache & Stats Generation
## 1. Generates the list of all required v0.8 data products
##    categorized by their type (3D_VIZ, STATS_AND_HISTO, STATS_ONLY).
## 2. v0.8: Generates 2 jobs (pos=0, pos=1) for every offset > 0.
## 3. v0.8: Re-introduces "Any" context.
## 4. v0.8: Skips all self-comparisons (e.g., phi vs phi).
## 5. v0.8: Skips redundant "Focal: X, Context: Any" jobs.

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

from tools.pipeline_utils import get_db_connection, get_invariant_limits
from tools.generate_visualizations import generate_visualization_data

from tools.pipeline_constants import (
    RESOLUTION_LEVELS, RESIDUE_CONTEXTS, ALL_INVARIANTS,
    TORSION_INVARIANTS, NON_TORSION_INVARIANTS
)

SCHEMA_V8_3D_CACHE = """
CREATE TABLE IF NOT EXISTS v8_3D_cache (
    plot_key TEXT PRIMARY KEY,
    data JSON NOT NULL
);
"""

SCHEMA_V8_HISTO_CACHE = """
CREATE TABLE IF NOT EXISTS v8_histo_cache (
    plot_key TEXT NOT NULL,
    axis TEXT NOT NULL,
    data JSON NOT NULL,
    PRIMARY KEY (plot_key, axis)
);
"""

SCHEMA_V8_STATS = """
CREATE TABLE IF NOT EXISTS v8_stats (
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
        df = pd.read_sql_query(f"SELECT plot_key FROM v8_stats", conn)
        return set(df['plot_key'])
    except pd.io.sql.DatabaseError:
        return set()

def drop_tables(conn):
    """Drops all cache and stats tables for a full recalculation."""
    print("WARNING: --recalculate flag set. Dropping cache and stats tables...")
    conn.execute("DROP TABLE IF EXISTS v8_3D_cache;")
    conn.execute("DROP TABLE IF EXISTS v8_histo_cache;")
    conn.execute("DROP TABLE IF EXISTS v8_stats;")
    # Drop old v7 tables just in case
    conn.execute("DROP TABLE IF EXISTS v7_3D_cache;")
    conn.execute("DROP TABLE IF EXISTS v7_histo_cache;")
    conn.execute("DROP TABLE IF EXISTS v7_stats;")
    print("Tables dropped.")


def process_job(job_args):
    """
    Worker function. Receives one job tuple and calls the 
    visualization tool to generate heatmap, unified stats, and 1D histograms.
    
    v0.8: job_args now includes 'pos' and 'res_level' (which can be None)
    
    Returns a tuple: 
    (job_key, job_type, cache_data, stats_data_tuple, histo_data_x, histo_data_y)
    """
    db_path, plot_key, job_type, inv1, offset, res1, inv2, res2, pos, res_level = job_args

    try:
        heatmap_data, stats_dict, histo_data_x, histo_data_y = generate_visualization_data(
            db_path, inv1, inv2, offset, res1, res2, res_level, pos,
            TORSION_INVARIANTS
        )
        
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
        
        return (
            plot_key, 
            job_type, 
            json.dumps(heatmap_data) if heatmap_data and res_level else None, 
            formatted_stats, 
            json.dumps(histo_data_x) if histo_data_x else None,
            json.dumps(histo_data_y) if histo_data_y else None
        )

    except Exception as e:
        return plot_key, "ERROR", None, (f"{type(e).__name__} - {e}",), None, None


def _write_batch_to_db(conn, results_3d_cache, results_1d_histo_cache, results_stats):
    """Helper function to write batches to the database in a transaction."""
    try:
        cursor = conn.cursor()
        
        if results_3d_cache:
            cursor.executemany("INSERT OR REPLACE INTO v8_3D_cache (plot_key, data) VALUES (?, ?)", results_3d_cache)
        
        if results_1d_histo_cache:
            cursor.executemany("INSERT OR REPLACE INTO v8_histo_cache (plot_key, axis, data) VALUES (?, ?, ?)", results_1d_histo_cache)
        
        if results_stats:
            cursor.executemany("""
                INSERT OR REPLACE INTO v8_stats 
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
            
        print("Ensuring v0.8 cache and stats tables exist...")
        conn.execute(SCHEMA_V8_3D_CACHE)
        conn.execute(SCHEMA_V8_HISTO_CACHE)
        conn.execute(SCHEMA_V8_STATS)
        
        completed_jobs = get_existing_keys(conn)
        print(f"Found {len(completed_jobs)} previously completed jobs.")
    
    jobs_to_run = []
    
    print("Generating v0.8 jobs based on categorization rules...")
    
    all_inv_pairs = list(product(ALL_INVARIANTS, ALL_INVARIANTS))
    all_res_pairs = list(product(RESIDUE_CONTEXTS, RESIDUE_CONTEXTS))
    all_offsets = range(5) ## Future: Have range be un-hardcoded
    
    total_combinations = len(all_inv_pairs) * len(all_res_pairs) * len(all_offsets)
    print(f"Checking {total_combinations} (9x9x21x21x5) total combinations...")

    count_3d_viz = 0
    count_stats_histo = 0
    count_stats_only = 0
    count_excluded_self = 0
    count_excluded_any = 0
    
    pbar = tqdm(total=total_combinations)
    for (inv1, inv2) in all_inv_pairs:
        # skip all self-comparisons (e.g., phi vs phi)
        if inv1 == inv2:
            count_excluded_self += len(all_res_pairs) * len(all_offsets)
            pbar.update(len(all_res_pairs) * len(all_offsets))
            continue

        for (res1, res2) in all_res_pairs:
            for offset in all_offsets:
                pbar.update(1)

                is_torsion_torsion = (inv1 in TORSION_INVARIANTS and inv2 in TORSION_INVARIANTS)
                is_other_other = (inv1 in NON_TORSION_INVARIANTS and inv2 in NON_TORSION_INVARIANTS)
                is_torsion_other = not is_torsion_torsion and not is_other_other
                
                if offset == 0:
                    job_type = "3D_VIZ"
                    pos = 0
                    res_level = RESOLUTION_LEVELS[0]
                    res2_placeholder = "NA" # res2 is not used at offset 0
                    plot_key = f"{offset}_{res1}_{res2_placeholder}_{pos}_{res_level}_{inv1}_vs_{inv2}"
                    
                    if plot_key not in completed_jobs:
                        jobs_to_run.append((db_path, plot_key, job_type, inv1, offset, res1, inv2, res2_placeholder, pos, res_level))
                    count_3d_viz += 1
                
                else:
                    # Offset > 0 jobs generate for both positions
                    for pos in [0, 1]:
                        # Redundancy check for "Focal: X, Context: Any"
                        if pos == 0 and res2 == 'Any':
                            count_excluded_any += 1
                            continue
                        if pos == 1 and res1 == 'Any':
                            count_excluded_any += 1
                            continue
                        
                        if is_torsion_torsion:
                            job_type = "3D_VIZ"
                            res_level = RESOLUTION_LEVELS[0]
                            plot_key = f"{offset}_{res1}_{res2}_{pos}_{res_level}_{inv1}_vs_{inv2}"
                            count_3d_viz += 1
                        
                        elif is_torsion_other:
                            job_type = "STATS_AND_HISTO"
                            res_level = None
                            plot_key = f"{offset}_{res1}_{res2}_{pos}_{inv1}_vs_{inv2}"
                            count_stats_histo += 1
                        
                        elif is_other_other:
                            job_type = "STATS_ONLY"
                            res_level = None
                            plot_key = f"{offset}_{res1}_{res2}_{pos}_{inv1}_vs_{inv2}"
                            count_stats_only += 1
                        
                        if plot_key not in completed_jobs:
                            jobs_to_run.append((db_path, plot_key, job_type, inv1, offset, res1, inv2, res2, pos, res_level))
    
    pbar.close()
    
    print("--- Job Generation Summary (v0.8) ---")
    print(f"Total Excluded (Self-Comparisons): {count_excluded_self}")
    print(f"Total Excluded (Redundant 'Any' Context): {count_excluded_any}")
    print(f"3D Visualization Jobs (3D_VIZ): {count_3d_viz}")
    print(f"Stats + 1D Histo Jobs (STATS_AND_HISTO): {count_stats_histo}")
    print(f"Stats Only Jobs (STATS_ONLY): {count_stats_only}")
    total_outputs = count_3d_viz + count_stats_histo + count_stats_only
    print(f"Total required outputs: {total_outputs}")

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
                
                results_stats.append(stats_data_tuple)

                if job_type == "3D_VIZ":
                    if cache_data:
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
                    pass

                if (i + 1) % BATCH_SIZE == 0:
                    _write_batch_to_db(conn, results_3d_cache, results_1d_histo_cache, results_stats)
                    results_3d_cache.clear()
                    results_1d_histo_cache.clear()
                    results_stats.clear()
            
            print("\nWriting final batch...")
            _write_batch_to_db(conn, results_3d_cache, results_1d_histo_cache, results_stats)
    
    if error_logs: 
        print(f"\n--- {len(error_logs)} Errors Encountered (or empty data sets) ---")
        for e in error_logs[:20]: print(e)
        if len(error_logs) > 20: print(f"...and {len(error_logs)-20} more.")

    end_time = time.time()
    print(f"Database insertion complete. Total script runtime: {time.time() - start_time:.2f}s.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the v8 data caching pipeline.")
    parser.add_argument("db_path", type=str, help="Path to the SQLite database.")
    parser.add_argument("--recalculate", action="store_true", help="Drop and recalculate all v8 cache and stats tables.")
    args = parser.parse_args()
    
    main(args.db_path, args.recalculate)