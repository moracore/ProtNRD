import json
import sqlite3
import pandas as pd
import numpy as np
from dash import Input, Output, State, no_update
import time
import math
from ..constants import (
    DB_PATH, INVARIANT_SHORTHAND, TORSION_INVARIANTS, 
    DB_COL_PREFIX_MAP
)

def get_triplet_rank_and_freq(conn, triplet):
    """
    Returns (frequency, rank) for a given triplet.
    Rank is calculated as 1 + count of triplets with higher population.
    """
    try:
        # 1. Get population for the target
        cursor = conn.execute("SELECT population FROM v9_3mer_map WHERE trimer = ?", (triplet,))
        row = cursor.fetchone()
        
        if not row:
            return None, None
            
        population = row[0]
        
        # 2. Get Rank (Count of rows with strictly greater population) + 1
        cursor = conn.execute("SELECT COUNT(*) FROM v9_3mer_map WHERE population > ?", (population,))
        rank = cursor.fetchone()[0] + 1
        
        return population, rank
    except Exception as e:
        print(f"Error fetching rank: {e}")
        return None, None

def get_triplet_and_plot_keys(res1, res2, res3, inv1, inv2, active_pos):
    """
    Constructs the lookup keys for the v9 database.
    """
    # Handle "Any" by defaulting to "A"
    r1 = res1 if res1 and res1 != "Any" else "A"
    r2 = res2 if res2 and res2 != "Any" else "A"
    r3 = res3 if res3 and res3 != "Any" else "A"

    triplet_key = f"{r1}{r2}{r3}"
    
    plot_key = None
    if inv1 and inv2:
        p1 = DB_COL_PREFIX_MAP.get(inv1, inv1)
        p2 = DB_COL_PREFIX_MAP.get(inv2, inv2)
        
        cache_map = {'phi': 'phi', 'psi': 'psi', 'omg': 'omega'}
        c1 = cache_map.get(p1, p1)
        c2 = cache_map.get(p2, p2)
        
        suffix = None
        s_set = {c1, c2}
        
        if s_set == {'phi', 'psi'}:
            suffix = 'phi_psi'
        elif s_set == {'phi', 'omega'}:
            suffix = 'phi_omega'
        elif s_set == {'psi', 'omega'}:
            suffix = 'psi_omega'
            
        if suffix:
            plot_key = f"{triplet_key}_p{active_pos}_{suffix}"
        
    return triplet_key, plot_key

def _extract_axis_stats(row, inv, axis_label, active_pos):
    """
    Extracts 1D stats, applying the 'pos{n}_' prefix to column lookups.
    """
    base_prefix = DB_COL_PREFIX_MAP.get(inv)
    if not base_prefix:
        return {}
    
    col_prefix = f"pos{active_pos}_{base_prefix}"
    std = row.get(f'{col_prefix}_std')
    
    if std is not None:
        variance = std**2
    else:
        variance = None
    
    return {
        f'mean_{axis_label}': row.get(f'{col_prefix}_mean'),
        f'std_{axis_label}': std,
        f'variance_{axis_label}': variance,
        f'min_{axis_label}': row.get(f'{col_prefix}_min'),
        f'max_{axis_label}': row.get(f'{col_prefix}_max'),
        f'median_{axis_label}': None, 
        f'peak_{axis_label}': row.get(f'{col_prefix}_peak'),
        f'peak_freq_{axis_label}': row.get(f'{col_prefix}_peak_f'),
        f'R_{axis_label}': row.get(f'{col_prefix}_R'),
        f'bin_{axis_label}': row.get(f'{col_prefix}_bin'),
        f'win_{axis_label}': row.get(f'{col_prefix}_win'),
        f'freq_at_mean_{axis_label}': None 
    }

def fetch_v9_data(conn, triplet_key, plot_key, inv1, inv2, active_pos):
    """
    Fetches data.
    """
    print(f"DEBUG: Fetching for {triplet_key}, Active Pos: {active_pos}, Plot Key: {plot_key}")

    # Fetch Aggregated Statistics
    stats_query = "SELECT * FROM stats WHERE [3mer] = ?"
    stats_df = pd.read_sql_query(stats_query, conn, params=(triplet_key,))

    if stats_df.empty:
        raise ValueError(f"No statistics found for triplet: {triplet_key}")

    stats_df = stats_df.replace({np.nan: None})

    row = stats_df.to_dict('records')[0]
    
    stats_data = {
        'population': row.get('frequency'),
        'covariance': None,
        'pearson_correlation': None,
        'peak_freq': None,
        'peak_x': None,
        'peak_y': None,
        'R2D': None,
        'mean_freq': None
    }
    
    stats_data.update(_extract_axis_stats(row, inv1, 'x', active_pos))
    stats_data.update(_extract_axis_stats(row, inv2, 'y', active_pos))
    
    prefix1 = DB_COL_PREFIX_MAP.get(inv1)
    prefix2 = DB_COL_PREFIX_MAP.get(inv2)
    pos_prefix = f"pos{active_pos}_"
    
    # Check for pairwise stats
    if (prefix1 == 'phi' and prefix2 == 'psi') or (prefix1 == 'psi' and prefix2 == 'phi'):
        stats_data['pearson_correlation'] = row.get(f'{pos_prefix}phi_psi_corr')
        stats_data['peak_freq'] = row.get(f'{pos_prefix}phi_psi_peak_f')
        stats_data['peak_x'] = row.get(f'{pos_prefix}phi_psi_peak_phi')
        stats_data['peak_y'] = row.get(f'{pos_prefix}phi_psi_peak_psi')
        stats_data['R2D'] = row.get(f'{pos_prefix}phi_psi_R2D')
        stats_data['mean_freq'] = row.get(f'{pos_prefix}phi_psi_mean_f')
        
    if stats_data['pearson_correlation'] is not None:
        std_x = row.get(f'{pos_prefix}{prefix1}_std')
        std_y = row.get(f'{pos_prefix}{prefix2}_std')
        
        if std_x is not None and std_y is not None:
            stats_data['covariance'] = stats_data['pearson_correlation'] * std_x * std_y
        else:
            stats_data['covariance'] = None

    all_data = {
        'stats_v9': stats_data,
        'job_type': 'STATS_ONLY',
        'figure_data_3d': None,
        'figure_data_histo_x': None, 
        'figure_data_histo_y': None
    }
    
    inv1_is_torsion = inv1 in TORSION_INVARIANTS
    inv2_is_torsion = inv2 in TORSION_INVARIANTS

    if inv1_is_torsion and inv2_is_torsion and plot_key:
        cache_query = "SELECT data FROM cache_3d WHERE plot_key = ?"
        cache_df = pd.read_sql_query(cache_query, conn, params=(plot_key,))
        
        if not cache_df.empty:
            try:
                parsed_data = json.loads(cache_df.iloc[0]['data'])
                if isinstance(parsed_data, dict):
                    # axis swap logic
                    db_x, db_y = None, None
                    if "_phi_psi" in plot_key:
                        db_x, db_y = 'phi', 'psi'
                    elif "_phi_omega" in plot_key:
                        db_x, db_y = 'phi', 'omega'
                    elif "_psi_omega" in plot_key:
                        db_x, db_y = 'psi', 'omega'
                    
                    def get_canonical(inv):
                        prefix = DB_COL_PREFIX_MAP.get(inv, inv)
                        if prefix in ['tau_NA', 'phi']: return 'phi'
                        if prefix in ['tau_AC', 'psi']: return 'psi'
                        if prefix in ['tau_CN', 'omg']: return 'omega'
                        return prefix
                    
                    user_x = get_canonical(inv1)
                    
                    if db_x and db_y and user_x == db_y:
                        parsed_data['x'], parsed_data['y'] = parsed_data.get('y', []), parsed_data.get('x', [])
                        if 'z' in parsed_data:
                            z_arr = np.array(parsed_data['z'])
                            if z_arr.ndim == 2:
                                parsed_data['z'] = z_arr.T.tolist()
                        if 'points' in parsed_data and parsed_data['points']:
                            try:
                                parsed_data['points'] = [[p[1], p[0], p[2]] for p in parsed_data['points']]
                            except (IndexError, TypeError):
                                pass
                                
                    all_data['figure_data_3d'] = parsed_data
                    all_data['job_type'] = '3D_VIZ'
            except (json.JSONDecodeError, TypeError) as e:
                print(f"ERROR decoding JSON for {plot_key}: {e}")

    return all_data

# Callbacks
def register_data_fetching_callbacks(app):
    
    @app.callback(
        Output('triplet-stats-container', 'children'),
        Input('triplet-input', 'value')
    )
    def update_triplet_stats_display(triplet_text):
        if not triplet_text or len(triplet_text) != 3:
            return ""
            
        triplet = triplet_text.upper()
        
        try:
            with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
                pop, rank = get_triplet_rank_and_freq(conn, triplet)
                
            if pop is not None:
                return f"Frequency: {pop:,} (Rank: #{rank})"
            else:
                return "Triplet not found in dataset"
        except Exception as e:
            return f"Error: {str(e)}"

    @app.callback(
        Output('panel-states-store', 'data'),
        Output('status-message-store', 'data', allow_duplicate=True),
        Output('query-warning-message', 'children'),
        Input('generate-graph-button', 'n_clicks'),
        State('inv1-dropdown', 'value'), State('inv2-dropdown', 'value'),
        State('triplet-input', 'value'), 
        State('position-dropdown', 'value'),
        State('xaxis-min-input', 'value'), State('xaxis-max-input', 'value'),
        State('yaxis-min-input', 'value'), State('yaxis-max-input', 'value'),
        State('scale-switch', 'value'),
        State('colormap-dropdown', 'value'),
        State('active-panel-store', 'data'),
        State('panel-states-store', 'data'), prevent_initial_call=True
    )
    def generate_panel_data(n_clicks, inv1, inv2, triplet_input, active_pos_val,
                            x_min, x_max, y_min, y_max,
                            scale_bool, colormap, active_panel_index, panel_states_json):
        panel_states = json.loads(panel_states_json or '{}')
        warning_message = ""

        try:
            if not triplet_input or len(triplet_input) < 3:
                 raise ValueError("Please enter a valid 3-letter triplet (e.g., AAA)")
            
            triplet_clean = triplet_input.upper()
            res1, res2, res3 = triplet_clean[0], triplet_clean[1], triplet_clean[2]

            active_pos = int(active_pos_val) if active_pos_val else 1
            
            triplet_key, plot_key = get_triplet_and_plot_keys(res1, res2, res3, inv1, inv2, active_pos)
            
            inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1)
            inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2)
            
            focus_res_char = [res1, res2, res3][active_pos-1]
            title = f"{inv1_label} vs {inv2_label} | {triplet_key} | Focus: Pos {active_pos} ({focus_res_char})"

            with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
                fetched_data = fetch_v9_data(conn, triplet_key, plot_key, inv1, inv2, active_pos)

            stats_v9 = fetched_data['stats_v9']
            job_type = fetched_data['job_type']

            new_panel_state = {
                'title': title, 
                'inv1': inv1, 'inv2': inv2, 
                'res1': res1, 'res2': res2, 'res3': res3,
                'x_lims': [x_min, x_max], 'y_lims': [y_min, y_max], 
                'uirevision_key': str(time.time()),
                'full_v8_stats': stats_v9,
                'log_scale': scale_bool,
                'colormap': colormap,
                'figure_data_histo': None 
            }

            if job_type == '3D_VIZ':
                new_panel_state['job_type'] = '3D_HEATMAP'
                new_panel_state['figure_data'] = fetched_data['figure_data_3d']
                new_panel_state['stats'] = {
                    'population': stats_v9.get('population'),
                    'peak_x': stats_v9.get('peak_x'),
                    'peak_y': stats_v9.get('peak_y'),
                    'peak_freq': stats_v9.get('peak_freq'),
                }
                new_panel_state['view'] = 'graph'

            elif job_type == 'STATS_ONLY':
                new_panel_state['job_type'] = '1D_STATS_VS_STATS'
                new_panel_state['figure_data_stats1'] = stats_v9 
                new_panel_state['figure_data_stats2'] = stats_v9 
                new_panel_state['view'] = 'stats'

            panel_states[str(active_panel_index)] = new_panel_state
            return json.dumps(panel_states), f"Panel {active_panel_index + 1} updated.", warning_message

        except ValueError as e:
            error_state = {'error': str(e), 'title': 'No Data'}
            panel_states[str(active_panel_index)] = error_state
            return json.dumps(panel_states), f"Error: {e}", ""
        except Exception as e:
            import traceback
            traceback.print_exc()
            error_state = {'error': str(e), 'title': 'Error'}
            panel_states[str(active_panel_index)] = error_state
            return json.dumps(panel_states), f"Error: {e}", ""