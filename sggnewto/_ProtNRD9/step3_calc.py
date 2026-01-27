import pandas as pd
import numpy as np
import sys
import os
import sqlite3
import json
import math
import time

# --- CONFIG ---
THR_FREQUENCY = 50  # Minimum population to generate a heatmap

# --- UTILS ---

def calculate_circular_stats(angles_deg):
    """Returns: [mean, R, std_dev, peak_val, peak_freq, f_bin, f_win]"""
    angles = np.array([a for a in angles_deg if a is not None], dtype=float)
    if len(angles) == 0: return [None]*7
    
    rads = np.radians(angles)
    x = np.cos(rads)
    y = np.sin(rads)
    mean_x, mean_y = np.mean(x), np.mean(y)
    R = np.sqrt(mean_x**2 + mean_y**2)
    mean_angle = np.degrees(np.arctan2(mean_y, mean_x))
    
    if mean_angle < -180: mean_angle += 360
    elif mean_angle > 180: mean_angle -= 360
    
    std = np.sqrt(-2 * np.log(R)) if R < 1 else 0
    
    # Peak detection (Simple histogram binning)
    hist, bin_edges = np.histogram(angles, bins=180, range=(-180, 180))
    peak_idx = np.argmax(hist)
    peak_val = (bin_edges[peak_idx] + bin_edges[peak_idx+1]) / 2
    
    return [mean_angle, R, std, peak_val, int(hist[peak_idx]), 0, 0]

def calculate_linear_stats(values):
    """Returns: [mean, std, min, max, peak, peak_f, f_bin, f_win]"""
    vals = np.array([v for v in values if v is not None], dtype=float)
    if len(vals) == 0: return [None]*8
    return [np.mean(vals), np.std(vals), np.min(vals), np.max(vals), np.median(vals), 0, 0, 0]

def calculate_2d_torsion_stats(phi, psi):
    """Returns global 2D stats (approximate implementation)"""
    valid = [(x,y) for x,y in zip(phi, psi) if x is not None and y is not None]
    if len(valid) < 2: return [None]*8
    vx, vy = zip(*valid)
    try:
        corr = np.corrcoef(vx, vy)[0,1]
    except:
        corr = 0
    return [np.mean(vx), np.mean(vy), corr, 0, 0, 0, 0, 0]

def generate_sparse_heatmap(df, x_col, y_col):
    """Generates JSON for 3D plot (sparse format: x, y, count)"""
    xs = df[x_col].dropna().values
    ys = df[y_col].dropna().values
    if len(xs) != len(ys) or len(xs) == 0: return json.dumps({})
    
    # 64x64 binning
    hist, xedges, yedges = np.histogram2d(xs, ys, bins=64, range=[[-180, 180], [-180, 180]])
    
    # Convert to sparse points (x, y, count)
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
        if idx % 100 == 0: print(f"[{idx}/{total}] Processing: {t_name}")
        
        # Fetch raw data for all 3 positions
        q = "SELECT * FROM '3mers' WHERE res_1=? AND res_2=? AND res_3=?"
        df = pd.read_sql_query(q, conn, params=(row['res_1'], row['res_2'], row['res_3']))
        
        if df.empty: continue
        
        # Initialize row with key and population
        current_stats = [t_name, int(row['population'])]
        
        # Loop through Position 1, 2, 3
        for pos in range(1, 4):
            # 1. 2D Stats
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
            
            # 4. Heatmaps (Only if high freq)
            if row['population'] >= THR_FREQUENCY:
                pairs = [
                    (f'tau_NA_{pos}', f'tau_AC_{pos}', 'phi_psi'),
                    (f'tau_NA_{pos}', f'tau_CN_{pos}', 'phi_omega'),
                    (f'tau_AC_{pos}', f'tau_CN_{pos}', 'psi_omega')
                ]
                for col_x, col_y, suffix in pairs:
                    try:
                        js = generate_sparse_heatmap(df, col_x, col_y)
                        # Key format: AAA_p1_phi_psi
                        key = f"{t_name}_p{pos}_{suffix}"
                        conn.execute("INSERT OR REPLACE INTO cache_3d VALUES (?, ?)", (key, js))
                    except Exception as e:
                        pass

        stats_data.append(tuple(current_stats))
    
    # Bulk Insert
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