import sqlite3

# ---------------------------------------------------------------------------
# Position-aware stats schema.
#
# The deployed proteins_v9.db `stats` table is keyed by [3mer] and stores EVERY
# metric three times, once per focus position, with a `pos1_`/`pos2_`/`pos3_`
# prefix (2 + 77*3 = 233 columns). The per-position 77-metric block, in order:
#
#   2D torsion (8): phi_psi_mean_phi, phi_psi_mean_psi, phi_psi_corr,
#                   phi_psi_R2D, phi_psi_peak_phi, phi_psi_peak_psi,
#                   phi_psi_peak_f, phi_psi_mean_f
#   torsions  (7 each): phi_*, psi_*, omg_*  -> mean,R,std,peak,peak_f,bin,win
#   lengths   (8 each): len_N_*, len_A_*, len_C_*
#   angles    (8 each): ang_N_*, ang_A_*, ang_C_*
#
# We build it programmatically so the column order/types stay in lock-step with
# the value tuple produced in 3_3M_cache.py.
# ---------------------------------------------------------------------------

_TWO_D = [
    ('phi_psi_mean_phi', 'REAL'), ('phi_psi_mean_psi', 'REAL'),
    ('phi_psi_corr', 'REAL'), ('phi_psi_R2D', 'REAL'),
    ('phi_psi_peak_phi', 'REAL'), ('phi_psi_peak_psi', 'REAL'),
    ('phi_psi_peak_f', 'INT'), ('phi_psi_mean_f', 'INT'),
]


def _circ(name):
    return [(f'{name}_mean', 'REAL'), (f'{name}_R', 'REAL'), (f'{name}_std', 'REAL'),
            (f'{name}_peak', 'REAL'), (f'{name}_peak_f', 'INT'),
            (f'{name}_bin', 'INT'), (f'{name}_win', 'INT')]


def _lin(name):
    return [(f'{name}_mean', 'REAL'), (f'{name}_std', 'REAL'), (f'{name}_min', 'REAL'),
            (f'{name}_max', 'REAL'), (f'{name}_peak', 'REAL'), (f'{name}_peak_f', 'INT'),
            (f'{name}_bin', 'INT'), (f'{name}_win', 'INT')]

# 8 + 7*3 + 8*6 = 77 metrics per position.
PER_POS_METRICS = (
    _TWO_D
    + _circ('phi') + _circ('psi') + _circ('omg')
    + _lin('len_N') + _lin('len_A') + _lin('len_C')
    + _lin('ang_N') + _lin('ang_A') + _lin('ang_C')
)

POSITIONS = (1, 2, 3)

# Full ordered (name, type) list including the two key columns.
STATS_COLUMNS = [('[3mer]', 'TEXT PRIMARY KEY'), ('frequency', 'INT')]
for _pos in POSITIONS:
    for _suf, _typ in PER_POS_METRICS:
        STATS_COLUMNS.append((f'pos{_pos}_{_suf}', _typ))

N_STATS_COLUMNS = len(STATS_COLUMNS)  # 2 + 77*3 = 233


def get_connection(db_path):
    """Returns a connection with a long timeout and performance pragmas."""
    conn = sqlite3.connect(db_path, timeout=3600)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=OFF;")
    conn.execute("PRAGMA cache_size=-2000000;")  # ~2GB cache
    return conn


def initialize_v9_tables(conn):
    """(Re)creates the position-aware stats table and the 3D heatmap cache."""
    conn.execute("DROP TABLE IF EXISTS stats;")
    conn.execute("DROP TABLE IF EXISTS cache_3d;")

    col_defs = ", ".join(f"{name} {typ}" for name, typ in STATS_COLUMNS)
    conn.execute(f"CREATE TABLE stats ({col_defs});")
    conn.execute("CREATE TABLE cache_3d (plot_key TEXT PRIMARY KEY, data JSON);")
    conn.commit()


def batch_insert_v9_stats(conn, entries):
    """Inserts a batch of fully-formed rows (each len == N_STATS_COLUMNS)."""
    if not entries:
        return
    placeholders = ",".join(["?"] * N_STATS_COLUMNS)
    conn.executemany(f"INSERT INTO stats VALUES ({placeholders})", entries)
    conn.commit()


def insert_heatmap(conn, plot_key, json_data):
    """Stores one sparse 3D heatmap JSON under a position-aware plot_key."""
    conn.execute("INSERT OR REPLACE INTO cache_3d (plot_key, data) VALUES (?, ?)",
                 (plot_key, json_data))
    conn.commit()
