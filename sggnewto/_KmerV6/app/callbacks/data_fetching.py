import json
import sqlite3
import pandas as pd
from dash import Input, Output, State, no_update
import time
from constants import (
    DB_PATH, INVARIANT_SHORTHAND, INVARIANT_ORDER,
    TORSION_INVARIANTS, NON_TORSION_INVARIANTS
)

# --- HELPER: v7 Key Generation ---

def get_plot_key_for_query(inv1, inv2, offset, res1, res2):
    """
    Determines the correct plot_key to query the v7 database.
    
    This is required because 3D_VIZ jobs have a '_level_1' suffix
    in their key, while stats-only jobs do not.
    """
    inv1_type = 'TORSION' if inv1 in TORSION_INVARIANTS else 'NON_TORSION'
    inv2_type = 'TORSION' if inv2 in TORSION_INVARIANTS else 'NON_TORSION'
    
    is_any_any = (res1 == 'Any' and res2 == 'Any')
    is_torsion_torsion = (inv1_type == 'TORSION' and inv2_type == 'TORSION')
    
    # Handle offset 0 sorting (same as old v6 logic)
    if (is_any_any or is_torsion_torsion) and offset == 0:
        try:
            idx1 = INVARIANT_ORDER.index(inv1)
            idx2 = INVARIANT_ORDER.index(inv2)
            if idx2 < idx1:
                inv1, inv2 = inv2, inv1 # Swap to match the key in the DB
        except ValueError:
            print(f"Warning: Invariant not found in INVARIANT_ORDER: {inv1} or {inv2}")
            
    if is_any_any or is_torsion_torsion:
        plot_key = f"{inv1}_vs_{inv2}+{offset}_{res1}_{res2}_level_1"
    else:
        plot_key = f"{inv1}_vs_{inv2}+{offset}_{res1}_{res2}"
        
    return plot_key

# --- HELPER: v7 Data Fetcher ---

def fetch_v7_data(conn, plot_key):
    """
    Fetches all available data for a single plot_key from the v7 DB.
    """
    print(f"DEBUG: Querying v7 database with plot_key: '{plot_key}'")
    
    stats_query = "SELECT * FROM v7_stats WHERE plot_key = ?"
    stats_df = pd.read_sql_query(stats_query, conn, params=(plot_key,))
    
    if stats_df.empty:
        print(f"DEBUG: No entry found in v7_stats for key '{plot_key}'")
        raise ValueError("No data found for this comparison (Population may be 0).")
        
    stats_data = stats_df.to_dict('records')[0]
    job_type = stats_data['job_type']
    
    all_data = {
        'stats': stats_data, # The full, unified v7 stats dictionary
        'job_type': job_type,
        'figure_data': None,
        'figure_data_histo_x': None,
        'figure_data_histo_y': None
    }
    
    if job_type == '3D_VIZ':
        cache_query = "SELECT data FROM v7_3D_cache WHERE plot_key = ?"
        cache_df = pd.read_sql_query(cache_query, conn, params=(plot_key,))
        if not cache_df.empty:
            all_data['figure_data'] = json.loads(cache_df.iloc[0]['data'])
        else:
            print(f"WARNING: No 3D_cache data found for 3D_VIZ job '{plot_key}'")

    if job_type == '3D_VIZ' or job_type == 'STATS_AND_HISTO':
        histo_query = "SELECT axis, data FROM v7_histo_cache WHERE plot_key = ?"
        histo_df = pd.read_sql_query(histo_query, conn, params=(plot_key,))
        
        for _, row in histo_df.iterrows():
            if row['axis'] == 'x':
                all_data['figure_data_histo_x'] = json.loads(row['data'])
            elif row['axis'] == 'y':
                all_data['figure_data_histo_y'] = json.loads(row['data'])

    return all_data

# --- HELPER: v7 to v6 Data Transformers ---

def _transform_v7_stats_to_v6_1d_stats(stats_v7, axis='x'):
    """
    Transforms the unified v7 stats dict into the old v6 1D stats
    format expected by create_stat_card.
    """
    if axis == 'y':
        return {
            'population': stats_v7.get('population'),
            'mean': stats_v7.get('mean_y'),
            'variance': stats_v7.get('variance_y'),
            'quartiles': {
                'min': stats_v7.get('min_y'),
                'median': stats_v7.get('median_y'),
                'max': stats_v7.get('max_y')
            }
        }
    else: # Default to 'x'
        return {
            'population': stats_v7.get('population'),
            'mean': stats_v7.get('mean_x'),
            'variance': stats_v7.get('variance_x'),
            'quartiles': {
                'min': stats_v7.get('min_x'),
                'median': stats_v7.get('median_x'),
                'max': stats_v7.get('max_x')
            }
        }

def _transform_v7_stats_to_v6_3d_overlay_stats(stats_v7):
    """
    Transforms the unified v7 stats dict into the old v6 3D stats
    format expected by the original build_3d_stats_overlay.
    """
    return {
        'population': stats_v7.get('population'),
        'peak_x': stats_v7.get('peak_x'),
        'peak_y': stats_v7.get('peak_y'),
        'peak_freq': stats_v7.get('peak_freq'),
        # Add 1D stats for the old overlay's "Mean (X, Y)" and "Variance (X, Y)"
        'mean_x': stats_v7.get('mean_x'),
        'mean_y': stats_v7.get('mean_y'),
        'variance_x': stats_v7.get('variance_x'),
        'variance_y': stats_v7.get('variance_y'),
    }


# --- CALLBACK FOR DATA FETCHING (Adapter Logic) ---

def register_data_fetching_callbacks(app):
    @app.callback(
        Output('panel-states-store', 'data'),
        Output('status-message-store', 'data', allow_duplicate=True),
        Input('generate-graph-button', 'n_clicks'),
        State('inv1-dropdown', 'value'),
        State('inv2-dropdown', 'value'),
        State('offset-dropdown', 'value'),
        State('res1-dropdown', 'value'),
        State('res2-dropdown', 'value'),
        State('xaxis-min-input', 'value'),
        State('xaxis-max-input', 'value'),
        State('yaxis-min-input', 'value'),
        State('yaxis-max-input', 'value'),
        State('active-panel-store', 'data'),
        State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def generate_panel_data(n_clicks, inv1, inv2, offset, res1, res2, x_min, x_max, y_min, y_max, active_panel_index, panel_states_json):
        """
        Triggered by 'Generate Graph'. Fetches data from the v7 DB,
        transforms it to the v6 format, and saves it to the store.
        """
        panel_states = json.loads(panel_states_json or '{}')

        try:
            # 1. Get the correct v7 plot key
            plot_key = get_plot_key_for_query(inv1, inv2, offset, res1, res2)
            
            # 2. Generate title (this logic is unchanged)
            inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1)
            inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2)
            res1_label = "" if res1 == 'Any' else f"({res1})"
            res2_label = "" if res2 == 'Any' else f"({res2})"
            title = f"{inv1_label}{res1_label} vs {inv2_label}{res2_label} +{offset}"

            # 3. Fetch all data from v7 DB
            with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
                all_data = fetch_v7_data(conn, plot_key)

            # 4. Build the new panel state, BUT using the OLD v6 structure
            new_panel_state = {
                'title': title,
                'inv1': inv1, 'inv2': inv2, 'offset': offset, 'res1': res1, 'res2': res2,
                'x_lims': [x_min, x_max], 'y_lims': [y_min, y_max],
                'uirevision_key': str(time.time()),
                
                # --- NEW: Store the full v7 stats for the modal ---
                'full_v7_stats': all_data['stats'] 
            }
            
            # 5. --- THIS IS THE FIX ---
            # Map v7 job types and data back to the old v6 structure
            
            v7_job_type = all_data['job_type']
            v7_stats = all_data['stats']
            
            if v7_job_type == '3D_VIZ':
                new_panel_state['job_type'] = '3D_HEATMAP'
                new_panel_state['figure_data'] = all_data['figure_data']
                # This 'stats' key holds the data for the *old overlay*
                new_panel_state['stats'] = _transform_v7_stats_to_v6_3d_overlay_stats(v7_stats)

            elif v7_job_type == 'STATS_AND_HISTO':
                inv1_is_torsion = inv1 in TORSION_INVARIANTS
                
                histo_data = all_data['figure_data_histo_x'] if inv1_is_torsion else all_data['figure_data_histo_y']
                stats_data = _transform_v7_stats_to_v6_1d_stats(v7_stats, axis='y' if inv1_is_torsion else 'x')

                if inv1_is_torsion:
                    new_panel_state['job_type'] = '1D_HISTO_VS_STATS'
                    new_panel_state['figure_data_histo'] = histo_data
                    # The stats for the histo (inv1) are also needed by its card
                    new_panel_state['stats_histo'] = _transform_v7_stats_to_v6_1d_stats(v7_stats, axis='x')
                    new_panel_state['figure_data_stats'] = stats_data # Used by create_stat_card
                else: # inv2 must be torsion
                    new_panel_state['job_type'] = '1D_STATS_VS_HISTO'
                    # The stats for the non-histo (inv1)
                    new_panel_state['figure_data_stats'] = _transform_v7_stats_to_v6_1d_stats(v7_stats, axis='x')
                    new_panel_state['figure_data_histo'] = histo_data
                    new_panel_state['stats_histo'] = _transform_v7_stats_to_v6_1d_stats(v7_stats, axis='y')
                    
            elif v7_job_type == 'STATS_ONLY':
                new_panel_state['job_type'] = '1D_STATS_VS_STATS'
                new_panel_state['figure_data_stats1'] = _transform_v7_stats_to_v6_1d_stats(v7_stats, axis='x')
                new_panel_state['figure_data_stats2'] = _transform_v7_stats_to_v6_1d_stats(v7_stats, axis='y')

            panel_states[str(active_panel_index)] = new_panel_state
            return json.dumps(panel_states), f"Panel {active_panel_index + 1} updated."

        except Exception as e:
            error_state = {'error': str(e), 'title': 'Error'}
            panel_states[str(active_panel_index)] = error_state
            print(f"ERROR during generate_panel_data: {e}")
            import traceback
            traceback.print_exc()
            return json.dumps(panel_states), f"Error: {e}"