import json
import pandas as pd
from ..constants import RESOLUTION_LEVELS, TORSION_INVARIANTS


def get_plot_key_for_query(inv1, inv2, offset, res1, res2, pos):
    if offset == 0:
        res2 = "NA"
        pos = 0

    inv1_type = 'TORSION' if inv1 in TORSION_INVARIANTS else 'NON_TORSION'
    inv2_type = 'TORSION' if inv2 in TORSION_INVARIANTS else 'NON_TORSION'

    is_torsion_torsion = (inv1_type == 'TORSION' and inv2_type == 'TORSION')

    if offset == 0 or is_torsion_torsion:
        res_level = RESOLUTION_LEVELS[0]
        plot_key = f"{offset}_{res1}_{res2}_{pos}_{res_level}_{inv1}_vs_{inv2}"
    else:
        plot_key = f"{offset}_{res1}_{res2}_{pos}_{inv1}_vs_{inv2}"

    return plot_key


def fetch_v8_data(conn, plot_key):
    print(f"DEBUG: Querying v8 database with plot_key: '{plot_key}'")

    stats_query = "SELECT * FROM v8_stats WHERE plot_key = ?"
    stats_df = pd.read_sql_query(stats_query, conn, params=(plot_key,))

    if stats_df.empty:
        raise ValueError("No data found for this comparison (Population may be 0).")

    stats_data = stats_df.to_dict('records')[0]
    job_type_v8 = stats_data['job_type']

    all_data = {
        'stats_v8': stats_data,
        'job_type_v8': job_type_v8,
        'figure_data_3d': None,
        'figure_data_histo_x': None,
        'figure_data_histo_y': None
    }

    if job_type_v8 == '3D_VIZ':
        cache_query = "SELECT data FROM v8_3D_cache WHERE plot_key = ?"
        cache_df = pd.read_sql_query(cache_query, conn, params=(plot_key,))
        if not cache_df.empty:
            try:
                parsed_data = json.loads(cache_df.iloc[0]['data'])
                if isinstance(parsed_data, dict):
                    all_data['figure_data_3d'] = parsed_data
            except (json.JSONDecodeError, TypeError) as e:
                print(f"ERROR decoding 3D cache JSON for '{plot_key}': {e}")

    if job_type_v8 == '3D_VIZ' or job_type_v8 == 'STATS_AND_HISTO':
        histo_query = "SELECT axis, data FROM v8_histo_cache WHERE plot_key = ?"
        histo_df = pd.read_sql_query(histo_query, conn, params=(plot_key,))

        for _, row in histo_df.iterrows():
            try:
                parsed_histo = json.loads(row['data'])
                if row['axis'] == 'x':
                    all_data['figure_data_histo_x'] = parsed_histo
                elif row['axis'] == 'y':
                    all_data['figure_data_histo_y'] = parsed_histo
            except (json.JSONDecodeError, TypeError) as e:
                print(f"ERROR decoding Histo cache JSON for '{plot_key}', axis {row['axis']}: {e}")

    return all_data
