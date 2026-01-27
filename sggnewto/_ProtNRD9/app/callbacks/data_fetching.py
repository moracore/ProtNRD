import json
import sqlite3
import pandas as pd
import struct
import math
from dash import Input, Output, State, no_update
import time
from constants import DB_PATH, INVARIANT_SHORTHAND

# Helper to map database invariants to cache key suffixes
CACHE_KEY_MAP = {
    'tau_NA': 'phi',
    'tau_AC': 'psi',
    'tau_CN': 'omega',
    'angle_N': 'angN',
    'angle_A': 'angA',
    'angle_C': 'angC',
    'length_NA': 'lenNA',
    'length_AC': 'lenAC',
    'length_CN': 'lenCN'
}

def fetch_v9_data(conn, triplet, inv1, inv2):
    """
    Fetches stats and cache for a triplet, dynamically looking for the 
    specific invariant pair (e.g., 'phi_omega') in the 3D cache.
    """
    
    # 1. Fetch Stats (Always valid for the triplet)
    stats_query = "SELECT * FROM stats WHERE [3mer] = ?"
    stats_df = pd.read_sql_query(stats_query, conn, params=(triplet,))

    if stats_df.empty:
        raise ValueError(f"No data found for {triplet}")

    stats_data = stats_df.to_dict('records')[0]

    # SANITIZATION: Robustly decode mixed Int64/Float64 blobs
    for key, val in stats_data.items():
        if isinstance(val, bytes):
            if len(val) == 8:
                try:
                    f_val = struct.unpack('<d', val)[0]
                    if math.isnan(f_val) or math.isinf(f_val):
                        i_val = struct.unpack('<q', val)[0]
                        if abs(i_val) < 10**12: 
                            stats_data[key] = i_val
                        else:
                            stats_data[key] = f_val
                    else:
                        stats_data[key] = f_val
                    continue
                except:
                    pass
            try:
                stats_data[key] = val.decode('utf-8')
            except:
                stats_data[key] = str(val)

    # 2. Fetch Heatmap dynamically based on selected invariants
    # Maps 'tau_NA' -> 'phi', 'tau_CN' -> 'omega' etc.
    suffix1 = CACHE_KEY_MAP.get(inv1, inv1)
    suffix2 = CACHE_KEY_MAP.get(inv2, inv2)
    
    # Construct key: e.g. "ALA_phi_omega" or "ALA_psi_omega"
    plot_key = f"{triplet}_{suffix1}_{suffix2}"
    
    cache_query = "SELECT data FROM cache_3d WHERE plot_key = ?"
    cache_df = pd.read_sql_query(cache_query, conn, params=(plot_key,))
    
    heatmap_data = None
    if not cache_df.empty:
        raw_blob = cache_df.iloc[0]['data']
        try:
            if isinstance(raw_blob, bytes):
                raw_blob = raw_blob.decode('utf-8')
            heatmap_data = json.loads(raw_blob)
        except Exception as e:
            print(f"Heatmap Decoding Error for {plot_key}: {e}")
            heatmap_data = None
            
    # Fallback: Try reverse key if symmetric? (Optional, usually we store one order)
    # If standard order is missing, you might want to try f"{triplet}_{suffix2}_{suffix1}"
    # but for now we stick to the primary requested order.

    return {'stats': stats_data, 'figure_data_3d': heatmap_data}

def register_data_fetching_callbacks(app):
    @app.callback(
        Output('panel-states-store', 'data'),
        Output('status-message-store', 'data', allow_duplicate=True),
        Output('query-warning-message', 'children'),
        Input('generate-graph-button', 'n_clicks'),
        State('res1-dropdown', 'value'), 
        State('res2-dropdown', 'value'), 
        State('res3-dropdown', 'value'),
        State('focus-position-store', 'data'),
        State('inv1-dropdown', 'value'), 
        State('inv2-dropdown', 'value'),
        State('xaxis-min-input', 'value'), State('xaxis-max-input', 'value'),
        State('yaxis-min-input', 'value'), State('yaxis-max-input', 'value'),
        State('scale-switch', 'value'),
        State('colormap-dropdown', 'value'),
        State('active-panel-store', 'data'),
        State('panel-states-store', 'data'), 
        prevent_initial_call=True
    )
    def generate_panel_data(n_clicks, r1, r2, r3, focus_pos, inv1, inv2, x_min, x_max, y_min, y_max,
                            scale_bool, colormap, active_panel_index, panel_states_json):
        panel_states = json.loads(panel_states_json or '{}')
        
        if focus_pos is None: focus_pos = 1

        if not (r1 and r2 and r3):
            return no_update, "Error: Select all 3 residues.", ""
        
        triplet = f"{r1}{r2}{r3}"

        try:
            with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
                # Pass inv1 and inv2 to dynamically fetch the correct heatmap
                fetched = fetch_v9_data(conn, triplet, inv1, inv2)

            # Check if we actually found 3D data for this specific pair
            has_3d_data = (fetched['figure_data_3d'] is not None)
            
            # Logic: If we found heatmap data, SHOW IT. 
            # We no longer restrict this to just phi/psi.
            show_graph = has_3d_data
            
            fig_data = fetched['figure_data_3d'] if show_graph else None
            
            inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1)
            inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2)

            new_panel_state = {
                'title': f"{triplet} (Focus: {focus_pos}): {inv1_label} vs {inv2_label}",
                'triplet': triplet,
                'focus_pos': focus_pos,
                'inv1': inv1,
                'inv2': inv2,
                'view': 'graph' if show_graph else 'stats', 
                'job_type': '3D_HEATMAP' if show_graph else 'STATS_ONLY',
                'x_lims': [x_min, x_max],
                'y_lims': [y_min, y_max],
                'log_scale': scale_bool,
                'colormap': colormap,
                'uirevision_key': str(time.time()),
                'full_stats': fetched['stats'],
                'figure_data': fig_data
            }

            panel_states[str(active_panel_index)] = new_panel_state
            
            msg = f"Loaded {triplet}"
            if not show_graph:
                msg += " (Stats View - No 3D Data)"

            return json.dumps(panel_states), msg, ""

        except Exception as e:
            print(f"FETCH ERROR: {e}")
            import traceback
            traceback.print_exc()
            return no_update, f"Error: {str(e)}", ""