import sqlite3

def get_connection(db_path):
    """Returns a connection with a long timeout and performance pragmas."""
    conn = sqlite3.connect(db_path, timeout=3600)
    # Performance tuning for high-volume 3-mer processing
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")
    conn.execute("PRAGMA cache_size=-2000000;") # ~2GB cache
    return conn

def initialize_v9_tables(conn):
    """Initializes the 79-column stats table and the 3D cache."""
    conn.execute("DROP TABLE IF EXISTS stats;")
    conn.execute("DROP TABLE IF EXISTS cache_3d;")
    
    conn.execute("""
        CREATE TABLE stats (
            [3mer] TEXT PRIMARY KEY, 
            frequency INT,
            
            -- Global 2D Stats (8 metrics)
            phi_psi_mean_phi REAL, phi_psi_mean_psi REAL, 
            phi_psi_corr REAL, phi_psi_R2D REAL,
            phi_psi_peak_phi REAL, phi_psi_peak_psi REAL, 
            phi_psi_peak_f INT, phi_psi_mean_f INT,
            
            -- Torsions (7 metrics each * 3 = 21)
            phi_mean REAL, phi_R REAL, phi_std REAL, phi_peak REAL, phi_peak_f INT, phi_f_bin INT, phi_f_win INT,
            psi_mean REAL, psi_R REAL, psi_std REAL, psi_peak REAL, psi_peak_f INT, psi_f_bin INT, psi_f_win INT,
            omg_mean REAL, omg_R REAL, omg_std REAL, omg_peak REAL, omg_peak_f INT, omg_f_bin INT, omg_f_win INT,
            
            -- Lengths (8 metrics each * 3 = 24)
            len_N_mean REAL, len_N_std REAL, len_N_min REAL, len_N_max REAL, len_N_peak REAL, len_N_peak_f INT, len_N_f_bin INT, len_N_f_win INT,
            len_A_mean REAL, len_A_std REAL, len_A_min REAL, len_A_max REAL, len_A_peak REAL, len_A_peak_f INT, len_A_f_bin INT, len_A_f_win INT,
            len_C_mean REAL, len_C_std REAL, len_C_min REAL, len_C_max REAL, len_C_peak REAL, len_C_peak_f INT, len_C_f_bin INT, len_C_f_win INT,
            
            -- Angles (8 metrics each * 3 = 24)
            ang_N_mean REAL, ang_N_std REAL, ang_N_min REAL, ang_N_max REAL, ang_N_peak REAL, ang_N_peak_f INT, ang_N_f_bin INT, ang_N_f_win INT,
            ang_A_mean REAL, ang_A_std REAL, ang_A_min REAL, ang_A_max REAL, ang_A_peak REAL, ang_A_peak_f INT, ang_A_f_bin INT, ang_A_f_win INT,
            ang_C_mean REAL, ang_C_std REAL, ang_C_min REAL, ang_C_max REAL, ang_C_peak REAL, ang_C_peak_f INT, ang_C_f_bin INT, ang_C_f_win INT
        );
    """)
    
    conn.execute("CREATE TABLE cache_3d (plot_key TEXT PRIMARY KEY, data JSON);")
    conn.commit()

def batch_insert_v9_stats(conn, entries):
    """Inserts batch into stats. 79 placeholders (3mer + freq + 77 metrics)."""
    if not entries:
        return
    placeholders = ",".join(["?"] * 79)
    conn.executemany(f"INSERT INTO stats VALUES ({placeholders})", entries)
    conn.commit()

def insert_heatmap(conn, plot_key, json_data):
    """Stores the sparse 3D heatmap JSON."""
    conn.execute("INSERT OR REPLACE INTO cache_3d (plot_key, data) VALUES (?, ?)", (plot_key, json_data))
    conn.commit()