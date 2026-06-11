import math
import os
import sys
import pandas as pd

from tools.pipeline_constants import THR_FREQUENCY
from tools.stats_utils import (
    calculate_2d_torsion_stats, calculate_circular_stats, calculate_linear_stats,
)
from tools.heatmap_utils import generate_sparse_heatmap
from tools.database_utils import (
    get_connection, initialize_v9_tables, batch_insert_v9_stats, insert_heatmap,
    PER_POS_METRICS, POSITIONS, N_STATS_COLUMNS,
)

# Torsion pairs cached as 3D heatmaps (base column names, position suffix added).
HEATMAP_PAIRS = [
    ('tau_NA', 'tau_AC', 'phi_psi'),    # Ramachandran
    ('tau_NA', 'tau_CN', 'phi_omega'),
    ('tau_AC', 'tau_CN', 'psi_omega'),
]

BATCH_SIZE = 500


def _coerce(value, sql_type):
    """None/NaN/Inf -> None; otherwise cast to the column's SQL type."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return int(round(f)) if sql_type == 'INT' else f


def _arr(df, col):
    return df[col].dropna().to_numpy(dtype=float)


def _position_block(df, pos):
    """Returns the 77 coerced stat values for one focus position, in schema order
    (matches tools.database_utils.PER_POS_METRICS)."""
    sub2d = df[[f'tau_NA_{pos}', f'tau_AC_{pos}']].dropna()
    g2d = calculate_2d_torsion_stats(
        sub2d[f'tau_NA_{pos}'].to_numpy(dtype=float),
        sub2d[f'tau_AC_{pos}'].to_numpy(dtype=float),
    )
    phi_s = calculate_circular_stats(_arr(df, f'tau_NA_{pos}'))
    psi_s = calculate_circular_stats(_arr(df, f'tau_AC_{pos}'))
    omg_s = calculate_circular_stats(_arr(df, f'tau_CN_{pos}'))
    l_na = calculate_linear_stats(_arr(df, f'length_NA_{pos}'), window=0.02)
    l_ac = calculate_linear_stats(_arr(df, f'length_AC_{pos}'), window=0.02)
    l_cn = calculate_linear_stats(_arr(df, f'length_CN_{pos}'), window=0.02)
    a_n = calculate_linear_stats(_arr(df, f'angle_N_{pos}'), window=5.0)
    a_a = calculate_linear_stats(_arr(df, f'angle_A_{pos}'), window=5.0)
    a_c = calculate_linear_stats(_arr(df, f'angle_C_{pos}'), window=5.0)

    raw = (list(g2d) + list(phi_s) + list(psi_s) + list(omg_s)
           + list(l_na) + list(l_ac) + list(l_cn)
           + list(a_n) + list(a_a) + list(a_c))
    assert len(raw) == len(PER_POS_METRICS), f"block len {len(raw)} != {len(PER_POS_METRICS)}"
    return [_coerce(v, t) for v, (_, t) in zip(raw, PER_POS_METRICS)]


def main(db_path):
    if not os.path.exists(db_path):
        sys.exit(f"Error: {db_path} not found.")

    conn = get_connection(db_path)
    print("--- Initializing position-aware v0.9 schema (stats + cache_3d) ---")
    initialize_v9_tables(conn)

    print("Fetching 3-mer targets from 'v9_3mer_map'...")
    try:
        targets = pd.read_sql_query("SELECT * FROM v9_3mer_map", conn)
    except Exception as e:
        sys.exit(f"Error reading 'v9_3mer_map'. Did 2_3M_freq.py run? {e}")

    total = len(targets)
    print(f"Processing {total} triplets...")
    stats_entries = []

    for idx, row in targets.iterrows():
        t_name = row['trimer']
        if idx % 100 == 0:
            print(f"[{idx}/{total}] {t_name}")

        df = pd.read_sql_query(
            "SELECT * FROM '3mers' WHERE res_1=? AND res_2=? AND res_3=?",
            conn, params=(row['res_1'], row['res_2'], row['res_3']),
        )
        if df.empty:
            continue

        # --- Stats: every metric, per focus position (pos1/pos2/pos3) ---
        entry = [t_name, int(row['population'])]
        for pos in POSITIONS:
            entry.extend(_position_block(df, pos))
        assert len(entry) == N_STATS_COLUMNS, f"row len {len(entry)} != {N_STATS_COLUMNS}"
        stats_entries.append(tuple(entry))

        # --- Heatmaps: per focus position, integer-degree bins ---
        if row['population'] >= THR_FREQUENCY:
            for pos in POSITIONS:
                for base_x, base_y, suffix in HEATMAP_PAIRS:
                    try:
                        hm = generate_sparse_heatmap(df, f'{base_x}_{pos}', f'{base_y}_{pos}')
                        insert_heatmap(conn, f'{t_name}_p{pos}_{suffix}', hm)
                    except Exception as e:
                        print(f"  skip {t_name}_p{pos}_{suffix}: {e}")

        if len(stats_entries) >= BATCH_SIZE:
            batch_insert_v9_stats(conn, stats_entries)
            stats_entries = []

    if stats_entries:
        batch_insert_v9_stats(conn, stats_entries)

    conn.close()
    print("Step 3 complete: position-aware stats + p1/p2/p3 integer-binned cache.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 3_3M_cache.py <db_path>")
    main(sys.argv[1])
