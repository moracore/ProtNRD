import pandas as pd
import numpy as np
import sys
import os
import sqlite3
import json
import math
import time

# --- CONFIG ---
THR_FREQUENCY = 1  # Minimum population to generate a heatmap

# --- MATH HELPERS ---

def get_clean_array(values):
    """Converts input to a float array and filters out None, NaN, and Inf."""
    arr = np.array(values, dtype=float)
    return arr[np.isfinite(arr)]

def get_circular_mean_R(angles_deg):
    """Calculates vector mean angle and mean resultant length (R)."""
    valid = get_clean_array(angles_deg)
    if len(valid) == 0:
        return None, None
    
    rads = np.radians(valid)
    x = np.cos(rads)
    y = np.sin(rads)
    
    mean_x = np.mean(x)
    mean_y = np.mean(y)
    
    R = np.sqrt(mean_x**2 + mean_y**2)
    
    # Avoid div by zero if R is 0
    if R == 0:
        return None, 0
        
    mean_angle = np.degrees(np.arctan2(mean_y, mean_x))
    return mean_angle, R

def get_histogram_peak_1d(values, is_circular=False, bins=360):
    """
    Finds the peak (mode) and frequency using histogram binning.
    """
    valid = get_clean_array(values)
    if len(valid) == 0:
        return None, 0, 0, 0

    range_lims = (-180, 180) if is_circular else (np.min(valid), np.max(valid))
    
    # Handle zero variance case for linear (min == max)
    if not is_circular and range_lims[0] == range_lims[1]:
        return valid[0], len(valid), 0, 0

    hist, bin_edges = np.histogram(valid, bins=bins, range=range_lims)
    peak_idx = np.argmax(hist)
    
    # Peak value is the center of the bin
    peak_val = (bin_edges[peak_idx] + bin_edges[peak_idx+1]) / 2
    peak_freq = int(hist[peak_idx])
    
    # Calculate bin size and window (placeholder for window)
    bin_size = bin_edges[1] - bin_edges[0]
    
    return peak_val, peak_freq, bin_size, bin_size # Window approx as bin size for now

def get_histogram_peak_2d(x_vals, y_vals, bins=64):
    """
    Finds the 2D peak (x, y) and frequency.
    Assumes circular data range (-180, 180).
    """
    # Robust NaN filtering for pairs
    xs = np.array(x_vals, dtype=float)
    ys = np.array(y_vals, dtype=float)
    mask = np.isfinite(xs) & np.isfinite(ys)
    
    xs = xs[mask]
    ys = ys[mask]
    
    if len(xs) == 0:
        return None, None, 0

    hist, xedges, yedges = np.histogram2d(xs, ys, bins=bins, range=[[-180, 180], [-180, 180]])
    
    # Unravel index of the max frequency
    ind = np.unravel_index(np.argmax(hist, axis=None), hist.shape)
    peak_freq = int(hist[ind])
    
    peak_x = (xedges[ind[0]] + xedges[ind[0]+1]) / 2
    peak_y = (yedges[ind[1]] + yedges[ind[1]+1]) / 2
    
    return peak_x, peak_y, peak_freq

# --- STATS CALCULATORS ---

def calculate_circular_stats(angles_deg):
    """
    Returns: [mean, R, std_dev, peak_val, peak_freq, f_bin, f_win]
    """
    mean_angle, R = get_circular_mean_R(angles_deg)
    
    if mean_angle is None: 
        return [None] * 7

    # Circular Standard Deviation: sqrt(-2 * ln(R))
    std = np.sqrt(-2 * np.log(R)) if (R is not None and R > 0 and R <= 1) else 0
    
    peak_val, peak_freq, bin_sz, win_sz = get_histogram_peak_1d(angles_deg, is_circular=True)
    
    return [mean_angle, R, std, peak_val, peak_freq, bin_sz, win_sz]

def calculate_linear_stats(values):
    """
    Returns: [mean, std, min, max, peak, peak_f, f_bin, f_win]
    """
    vals = get_clean_array(values)
    if len(vals) == 0: 
        return [None] * 8
        
    mean_val = np.mean(vals)
    std_val = np.std(vals)
    min_val = np.min(vals)
    max_val = np.max(vals)
    
    peak_val, peak_freq, bin_sz, win_sz = get_histogram_peak_1d(values, is_circular=False, bins=50)
    
    return [mean_val, std_val, min_val, max_val, peak_val, peak_freq, bin_sz, win_sz]

def calculate_2d_torsion_stats(phi, psi):
    """
    Returns: [mean_phi, mean_psi, corr, R2D_unused, peak_phi, peak_psi, peak_f, mean_f_unused]
    """
    # Filter for valid pairs
    phi_arr = np.array(phi, dtype=float)
    psi_arr = np.array(psi, dtype=float)
    mask = np.isfinite(phi_arr) & np.isfinite(psi_arr)
    
    phi_valid = phi_arr[mask]
    psi_valid = psi_arr[mask]
    
    if len(phi_valid) == 0:
        return [None] * 8
        
    # Circular Means
    mean_phi, _ = get_circular_mean_R(phi_valid)
    mean_psi, _ = get_circular_mean_R(psi_valid)
    
    # Correlation
    try:
        corr = np.corrcoef(phi_valid, psi_valid)[0, 1]
    except:
        corr = 0
        
    # Peak Detection
    peak_x, peak_y, peak_f = get_histogram_peak_2d(phi_valid, psi_valid)
    
    return [mean_phi, mean_psi, corr, 0, peak_x, peak_y, peak_f, 0]

def generate_sparse_heatmap(df, x_col, y_col):
    """Generates JSON for 3D plot (sparse format: x, y, count)"""
    temp_df = df[[x_col, y_col]].dropna()
    
    if temp_df.empty: 
        return json.dumps({})
    
    xs = temp_df[x_col].values
    ys = temp_df[y_col].values
    
    # 64x64 binning
    hist, xedges, yedges = np.histogram2d(xs, ys, bins=64, range=[[-180, 180], [-180, 180]])
    
    x_centers = (xedges[:-1] + xedges[1:]) / 2
    y_centers = (yedges[:-1] + yedges[1:]) / 2
    
    points = []
    xv, yv = np.meshgrid(x_centers, y_centers)
    for i in range(hist.shape[0]):     
        for j in range(hist.shape[1]): 
            val = hist[i, j]
            if val > 0:
                points.append((float(xv[i,j]), float(yv[i,j]), int(val)))
                
    return json.dumps({'points': points})

def initialize_v9_tables(conn):
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS stats")
    c.execute("DROP TABLE IF EXISTS cache_3d")
    
    # Create columns with position prefixes (pos1_, pos2_, pos3_)
    cols = ["'3mer' TEXT PRIMARY KEY", "frequency INT"]
    
    metrics = ['mean', 'R', 'std', 'peak', 'peak_f', 'bin', 'win']
    metrics_lin = ['mean', 'std', 'min', 'max', 'peak', 'peak_f', 'bin', 'win']
    
    tors = ['phi', 'psi', 'omg']
    lens = ['len_N', 'len_A', 'len_C']
    angs = ['ang_N', 'ang_A', 'ang_C']
    
    # Loop for each position (1, 2, 3)
    for pos in range(1, 4):
        p_prefix = f"pos{pos}_"
        
        # 2D stats
        cols.extend([f"{p_prefix}phi_psi_mean_phi REAL", f"{p_prefix}phi_psi_mean_psi REAL", 
                     f"{p_prefix}phi_psi_corr REAL", f"{p_prefix}phi_psi_R2D REAL", 
                     f"{p_prefix}phi_psi_peak_phi REAL", f"{p_prefix}phi_psi_peak_psi REAL", 
                     f"{p_prefix}phi_psi_peak_f INT", f"{p_prefix}phi_psi_mean_f INT"])
        
        # Circular Metrics
        for t in tors:
            for m in metrics: cols.append(f"{p_prefix}{t}_{m} REAL")
        
        # Linear Metrics
        for l in lens + angs:
            for m in metrics_lin: cols.append(f"{p_prefix}{l}_{m} REAL")
        
    c.execute(f"CREATE TABLE stats ({', '.join(cols)})")
    c.execute("CREATE TABLE cache_3d (plot_key TEXT PRIMARY KEY, data JSON)")
    conn.commit()

# --- MAIN ---

def main(db_path):
    print("--- Step 3: Calculation & Caching (All 3 Positions) ---")
    if not os.path.exists(db_path): sys.exit(f"Error: {db_path} not found.")

    conn = sqlite3.connect(db_path, timeout=600)
    initialize_v9_tables(conn)
    
    try:
        targets = pd.read_sql_query("SELECT * FROM v9_3mer_map", conn)
    except Exception as e:
        sys.exit(f"Error reading 'v9_3mer_map'. Did Step 2 run? Error: {e}")

    total = len(targets)
    print(f"Processing {total} unique triplets...")
    
    stats_data = []
    
    for idx, row in targets.iterrows():
        t_name = row['trimer']
        
        # Verbose logging
        is_verbose = (idx < 10) or (idx % 100 == 0)
        
        if is_verbose: 
            print(f"[{idx}/{total}] Processing: {t_name}")
            t_start_fetch = time.time()
        
        # Fetch raw data for all 3 positions
        q = "SELECT * FROM '3mers' WHERE res_1=? AND res_2=? AND res_3=?"
        df = pd.read_sql_query(q, conn, params=(row['res_1'], row['res_2'], row['res_3']))
        
        if is_verbose:
            print(f"  > Fetch: {len(df)} rows in {time.time() - t_start_fetch:.3f}s")
        
        if df.empty: continue
        
        # Initialize row with key and population
        current_stats = [t_name, int(row['population'])]
        
        # Loop through Position 1, 2, 3
        for pos in range(1, 4):
            if is_verbose: 
                print(f"  > Calc Pos {pos}...", end="", flush=True)
                t_start_pos = time.time()

            # 1. 2D Stats (Phi/Psi)
            g2d = calculate_2d_torsion_stats(df[f'tau_NA_{pos}'], df[f'tau_AC_{pos}'])
            current_stats.extend(g2d)
            
            # 2. Torsions
            current_stats.extend(calculate_circular_stats(df[f'tau_NA_{pos}']))
            current_stats.extend(calculate_circular_stats(df[f'tau_AC_{pos}']))
            current_stats.extend(calculate_circular_stats(df[f'tau_CN_{pos}']))
            
            # 3. Lengths/Angles
            current_stats.extend(calculate_linear_stats(df[f'length_NA_{pos}']))
            current_stats.extend(calculate_linear_stats(df[f'length_AC_{pos}']))
            current_stats.extend(calculate_linear_stats(df[f'length_CN_{pos}']))
            current_stats.extend(calculate_linear_stats(df[f'angle_N_{pos}']))
            current_stats.extend(calculate_linear_stats(df[f'angle_A_{pos}']))
            current_stats.extend(calculate_linear_stats(df[f'angle_C_{pos}']))
            
            if is_verbose: print(f" Done ({time.time() - t_start_pos:.3f}s)")

            # 4. Heatmaps
            if row['population'] >= THR_FREQUENCY:
                pairs = [
                    (f'tau_NA_{pos}', f'tau_AC_{pos}', 'phi_psi'),
                    (f'tau_NA_{pos}', f'tau_CN_{pos}', 'phi_omega'),
                    (f'tau_AC_{pos}', f'tau_CN_{pos}', 'psi_omega')
                ]
                for col_x, col_y, suffix in pairs:
                    try:
                        js = generate_sparse_heatmap(df, col_x, col_y)
                        key = f"{t_name}_p{pos}_{suffix}"
                        conn.execute("INSERT OR REPLACE INTO cache_3d VALUES (?, ?)", (key, js))
                    except Exception as e:
                        pass

        stats_data.append(tuple(current_stats))
    
    if stats_data:
        print("Finalizing stats insertion...")
        placeholders = ",".join(["?"] * len(stats_data[0]))
        conn.executemany(f"INSERT INTO stats VALUES ({placeholders})", stats_data)
        conn.commit()
    
    print("Step 3 Complete.")
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit("Usage: python3 step3_calc.py <db_path>")
    main(sys.argv[1])