import json
import plotly.io as pio
from dash import dcc, html, Input, Output, State, no_update, ctx, ALL, MATCH
import dash_bootstrap_components as dbc
from .rendering import create_3D_figure, create_1D_histo_figure, build_full_stats_table
from .data_fetching import fetch_v9_data, get_triplet_and_plot_keys
from constants import (
    INVARIANT_SHORTHAND, TORSION_INVARIANTS, INVARIANT_ORDER, 
    NON_TORSION_INVARIANTS, AMINO_ACID_NAMES, DB_PATH
)
import io
import csv
import numpy as np
import urllib.parse
import re
import sqlite3
import time

# --- Shortcode Mapping ---
# Maps long invariant names to single characters for URL compression
# User Request: p=phi, y=psi, w=omega
SHORTCODE_MAP = {
    'tau_NA': 'p', 'tau_AC': 'y', 'tau_CN': 'w',   # Torsions
    'angle_N': 'a', 'angle_A': 'b', 'angle_C': 'c', # Angles
    'length_NA': 'l', 'length_AC': 'm', 'length_CN': 'n' # Lengths
}
REVERSE_SHORTCODE_MAP = {v: k for k, v in SHORTCODE_MAP.items()}

def format_stat_value(value, use_sci_notation=False, precision=3):
    """Formats a numeric value either as fixed-point or scientific notation"""
    if value is None:
        return "N/A"
    try:
        if use_sci_notation:
            return f"{value:.{precision}e}"
        else:
            if abs(value) < 1e-4 and abs(value) > 0:
                return f"{value:.{precision}e}"
            return f"{value:.{precision}f}"
    except (TypeError, ValueError):
        return str(value)

def create_stats_csv(panel_state: dict, use_sci_notation: bool = False) -> str:
    """Converts the full_v8_stats dictionary to a CSV string"""
    stats_data = panel_state.get('full_v8_stats')
    if not stats_data:
        return ""
    
    inv1 = panel_state.get('inv1', 'X')
    inv2 = panel_state.get('inv2', 'Y')
    inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1)
    inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2)

    stat_order = [
        ('population', 'Population'),
        ('mean_x', f'Mean ({inv1_label})'),
        ('mean_y', f'Mean ({inv2_label})'),
        ('variance_x', f'Variance ({inv1_label})'),
        ('variance_y', f'Variance ({inv2_label})'),
        ('freq_at_mean_x', f'Freq. at Mean ({inv1_label})'),
        ('freq_at_mean_y', f'Freq. at Mean ({inv2_label})'),
        ('median_x', f'Median ({inv1_label})'),
        ('median_y', f'Median ({inv2_label})'),
        ('min_x', f'Min ({inv1_label})'),
        ('min_y', f'Min ({inv2_label})'),
        ('max_x', f'Max ({inv1_label})'),
        ('max_y', f'Max ({inv2_label})'),
        ('covariance', 'Covariance'),
        ('pearson_correlation', 'Pearson Correlation'),
        ('peak_x', f'Peak ({inv1_label})'),
        ('peak_y', f'Peak ({inv2_label})'),
        ('peak_freq', 'Peak Frequency'),
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Statistic', 'Value'])
    
    for key, friendly_name in stat_order:
        value = stats_data.get(key)
        
        if value is None:
            value_str = "N/A"
        elif isinstance(value, (int, np.integer)):
            value_str = f"{value:,}"
        elif isinstance(value, (float, np.floating)):
            prec = 4 if key == 'pearson_correlation' else 3
            value_str = format_stat_value(value, use_sci_notation, precision=prec)
        else:
            value_str = str(value)
            
        writer.writerow([friendly_name, value_str])
        
    return output.getvalue()


def register_interaction_callbacks(app):

    @app.callback(
        Output('share-url-box', 'value'),
        Input('panel-states-store', 'data')
    )
    def update_share_url(panel_states_json):
        """Generates the simplified URL based on current state."""
        if not panel_states_json:
            return ""
        
        panel_states = json.loads(panel_states_json)
        encoded_parts = []
        
        # We need to construct a string for all 6 panels.
        # If a panel is missing (e.g. 0, 1 exists, 2 missing, 3 exists), we use empty strings.
        max_idx = max([int(k) for k in panel_states.keys()]) if panel_states else -1
        
        # Only generate up to the last active panel to keep URL short
        for i in range(max_idx + 1):
            if str(i) not in panel_states:
                encoded_parts.append("") # Empty slot -> "_"
                continue
                
            state = panel_states[str(i)]
            res1 = state.get('res1', 'A')
            res2 = state.get('res2', 'A')
            res3 = state.get('res3', 'A')
            
            # Extract Focus Pos
            title = state.get('title', '')
            pos = 1
            if "Focus: Pos 2" in title: pos = 2
            elif "Focus: Pos 3" in title: pos = 3
            elif state.get('focus_pos'): pos = state.get('focus_pos') # Fallback if we saved it
            
            inv1 = state.get('inv1', 'tau_NA')
            inv2 = state.get('inv2', 'tau_AC')
            view = state.get('view', 'graph')
            
            # Map to short codes
            c1 = SHORTCODE_MAP.get(inv1, 'p')
            c2 = SHORTCODE_MAP.get(inv2, 'y')
            v_char = 'g' if view == 'graph' else 's'
            
            # Format: AAA1pyg (7 chars)
            segment = f"{res1}{res2}{res3}{pos}{c1}{c2}{v_char}"
            encoded_parts.append(segment)
            
        # Join with '_'
        # Example: AAA1pyg_AAA2wws__GAP1pyg
        q_string = "_".join(encoded_parts)
        if not q_string: return ""
        
        return f"?q={q_string}"

    @app.callback(
        Output('panel-states-store', 'data', allow_duplicate=True),
        Input('url', 'search'),
        State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def load_state_from_url(search, current_store_json):
        if not search:
            return no_update
        
        try:
            clean_search = search.lstrip('?').strip()
            panel_states = json.loads(current_store_json or '{}')
            updated = False

            # --- MODE 1: 3-MER MAGIC (e.g. "?GAP") ---
            if re.match(r'^[A-Za-z]{3}$', clean_search):
                res1, res2, res3 = list(clean_search.upper())
                inv1, inv2 = 'tau_NA', 'tau_AC'
                
                with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
                    for i in range(6):
                        if i < 3:
                            view = 'graph'
                            focus_pos = i + 1
                        else:
                            view = 'stats'
                            focus_pos = i - 2

                        triplet_key, plot_key = get_triplet_and_plot_keys(res1, res2, res3, inv1, inv2, focus_pos)
                        try:
                            fetched_data = fetch_v9_data(conn, triplet_key, plot_key, inv1, inv2, focus_pos)
                            stats_v9 = fetched_data['stats_v9']
                            job_type = fetched_data['job_type']
                            
                            focus_char = [res1, res2, res3][focus_pos-1]
                            title = f"{INVARIANT_SHORTHAND.get(inv1, inv1)} vs {INVARIANT_SHORTHAND.get(inv2, inv2)} | {triplet_key} | Focus: Pos {focus_pos} ({focus_char})"
                            
                            new_state = {
                                'title': title,
                                'inv1': inv1, 'inv2': inv2,
                                'res1': res1, 'res2': res2, 'res3': res3,
                                'x_lims': [None, None], 'y_lims': [None, None],
                                'log_scale': True,
                                'colormap': 'Custom Rainbow',
                                'uirevision_key': str(time.time()),
                                'full_v8_stats': stats_v9,
                                'view': view,
                                'focus_pos': focus_pos # Save for URL generation
                            }

                            if job_type == '3D_VIZ':
                                new_state['job_type'] = '3D_HEATMAP'
                                new_state['figure_data'] = fetched_data['figure_data_3d']
                                new_state['stats'] = {
                                    'population': stats_v9.get('population'),
                                    'peak_x': stats_v9.get('peak_x'),
                                    'peak_y': stats_v9.get('peak_y'),
                                    'peak_freq': stats_v9.get('peak_freq'),
                                }
                            else:
                                new_state['job_type'] = '1D_STATS_VS_STATS'
                                new_state['figure_data_stats1'] = stats_v9
                                new_state['figure_data_stats2'] = stats_v9

                            panel_states[str(i)] = new_state
                            updated = True
                            
                        except Exception as e:
                            print(f"Error fetching data for panel {i} (shortcut): {e}")

                if updated:
                    return json.dumps(panel_states)

            # --- MODE 2: SHORTCODES (e.g. "?q=AAA1pyg_GAP2wws") ---
            parsed_url = urllib.parse.urlparse(search)
            query_params = urllib.parse.parse_qs(parsed_url.query)
            
            if 'q' in query_params:
                q_string = query_params['q'][0]
                segments = q_string.split('_')
                
                with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
                    for i, seg in enumerate(segments):
                        if i >= 6: break
                        
                        # Empty segment (caused by __) means clear/skip this panel
                        if not seg:
                            continue
                        
                        # Expected format: AAA1pyg (Len 7)
                        # Res(3) Pos(1) Inv1(1) Inv2(1) View(1)
                        if len(seg) == 7:
                            res1, res2, res3 = seg[0], seg[1], seg[2]
                            try:
                                focus_pos = int(seg[3])
                            except:
                                focus_pos = 1
                                
                            c1 = seg[4]
                            c2 = seg[5]
                            v_char = seg[6]
                            
                            inv1 = REVERSE_SHORTCODE_MAP.get(c1, 'tau_NA')
                            inv2 = REVERSE_SHORTCODE_MAP.get(c2, 'tau_AC')
                            view = 'graph' if v_char == 'g' else 'stats'
                            
                            # FETCH DATA
                            triplet_key, plot_key = get_triplet_and_plot_keys(res1, res2, res3, inv1, inv2, focus_pos)
                            try:
                                fetched_data = fetch_v9_data(conn, triplet_key, plot_key, inv1, inv2, focus_pos)
                                stats_v9 = fetched_data['stats_v9']
                                job_type = fetched_data['job_type']
                                
                                focus_char = [res1, res2, res3][focus_pos-1] if focus_pos <= 3 else "?"
                                title = f"{INVARIANT_SHORTHAND.get(inv1, inv1)} vs {INVARIANT_SHORTHAND.get(inv2, inv2)} | {res1}{res2}{res3} | Focus: Pos {focus_pos} ({focus_char})"
                                
                                new_state = {
                                    'title': title,
                                    'inv1': inv1, 'inv2': inv2,
                                    'res1': res1, 'res2': res2, 'res3': res3,
                                    'x_lims': [None, None], 'y_lims': [None, None],
                                    'log_scale': True,
                                    'colormap': 'Custom Rainbow',
                                    'uirevision_key': str(time.time()),
                                    'full_v8_stats': stats_v9,
                                    'view': view,
                                    'focus_pos': focus_pos
                                }
                                
                                if job_type == '3D_VIZ':
                                    new_state['job_type'] = '3D_HEATMAP'
                                    new_state['figure_data'] = fetched_data['figure_data_3d']
                                    new_state['stats'] = {
                                        'population': stats_v9.get('population'),
                                        'peak_x': stats_v9.get('peak_x'),
                                        'peak_y': stats_v9.get('peak_y'),
                                        'peak_freq': stats_v9.get('peak_freq'),
                                    }
                                else:
                                    new_state['job_type'] = '1D_STATS_VS_STATS'
                                    new_state['figure_data_stats1'] = stats_v9
                                    new_state['figure_data_stats2'] = stats_v9

                                panel_states[str(i)] = new_state
                                updated = True
                            except Exception as e:
                                print(f"Error fetching data for shortcode panel {i}: {e}")

                if updated:
                    return json.dumps(panel_states)

            return no_update

        except Exception as e:
            print(f"Error parsing URL: {e}")
            import traceback
            traceback.print_exc()
            return no_update

    @app.callback(
        Output('sci-notation-store', 'data'),
        Input('sci-notation-switch', 'value')
    )
    def update_sci_notation_store(switch_value):
        return switch_value

    @app.callback(
        Output('xaxis-limit-label', 'children'),
        Output('yaxis-limit-label', 'children'),
        Input('inv1-dropdown', 'value'),
        Input('inv2-dropdown', 'value')
    )
    def update_axis_labels(inv1, inv2):
        inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1); inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2);
        xaxis_text = f"{inv1_label}-axis limits"; yaxis_text = f"{inv2_label}-axis limits";
        return xaxis_text, yaxis_text

    @app.callback(
        Output('active-panel-store', 'data'), Output('active-panel-display', 'children'),
        Output('inv1-dropdown', 'value'), Output('inv2-dropdown', 'value'),
        Output('triplet-input', 'value'), Output('position-dropdown', 'value'),
        Output('xaxis-min-input', 'value'), Output('xaxis-max-input', 'value'), 
        Output('yaxis-min-input', 'value'), Output('yaxis-max-input', 'value'),
        Output('scale-switch', 'value'),
        Output('colormap-dropdown', 'value'),
        Output('sci-notation-switch', 'value'),
        Input({'type': 'config-button', 'index': ALL}, 'n_clicks'),
        Input({'type': 'placeholder-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        State('sci-notation-store', 'data'),
        prevent_initial_call=True
    )
    def update_active_panel(config_clicks, placeholder_clicks, panel_states_json, sci_notation_pref):
        triggered_id_dict = ctx.triggered_id;
        
        # Default State (Fresh Panel)
        default_return = (
            0, "Configure Panel 1", 
            'tau_NA', 'tau_AC', 
            'AAA', 1,    # Triplet, Position
            None, None, None, None, 
            True, 'Custom Rainbow', sci_notation_pref or False
        )

        if not triggered_id_dict:
            config_triggered = any(c is not None for c in config_clicks)
            placeholder_triggered = any(p is not None for p in placeholder_clicks)
            if not config_triggered and not placeholder_triggered: 
                return default_return
            else: return no_update

        try:
            if isinstance(triggered_id_dict, dict) and 'index' in triggered_id_dict: 
                active_panel_index = triggered_id_dict['index']
            elif 'prop_id' in triggered_id_dict: 
                prop_id_str = triggered_id_dict['prop_id'].split('.')[0]
                parsed_id = json.loads(prop_id_str.replace("'", '"'))
                active_panel_index = parsed_id['index']
            else: 
                print(f"Unexpected triggered_id format: {triggered_id_dict}")
                return no_update
        except Exception as e: 
            print(f"Error parsing triggered_id: {triggered_id_dict} - {e}")
            return no_update
        
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(active_panel_index))
        
        # Restore state or use defaults
        inv1 = state.get('inv1', 'tau_NA') if state else 'tau_NA'
        inv2 = state.get('inv2', 'tau_AC') if state else 'tau_AC'
        
        res1 = state.get('res1', 'A') if state else 'A'
        res2 = state.get('res2', 'A') if state else 'A'
        res3 = state.get('res3', 'A') if state else 'A'
        triplet_str = f"{res1}{res2}{res3}"
        
        # Restore active position from title (fallback method)
        title = state.get('title', '')
        pos_val = 1
        if "Focus: Pos 2" in title:
            pos_val = 2
        elif "Focus: Pos 3" in title:
            pos_val = 3

        x_lims = state.get('x_lims', [None, None]) if state else [None, None]
        y_lims = state.get('y_lims', [None, None]) if state else [None, None]
        log_scale = state.get('log_scale', True) if state else True
        colormap = state.get('colormap', 'Custom Rainbow') if state else 'Custom Rainbow'

        return (
            active_panel_index, f"Configure Panel {active_panel_index + 1}", 
            inv1, inv2, 
            triplet_str, pos_val,
            x_lims[0], x_lims[1], y_lims[0], y_lims[1],
            log_scale, colormap, sci_notation_pref or False
        )

    @app.callback(
        Output('res1-container', 'style'),
        Output('res2-container', 'style'),
        Output('res3-container', 'style'),
        Output('visual-options-container', 'style'),
        Output('xaxis-limit-container', 'style'),
        Output('yaxis-limit-container', 'style'),
        Output('colormap-container', 'style'),
        Output('scale-switch-container', 'style'),
        Output('inv1-dropdown', 'options'),
        Output('inv2-dropdown', 'options'),
        Input('inv1-dropdown', 'value'),
        Input('inv2-dropdown', 'value')
    )
    def manage_config_panel_layout(inv1, inv2):
        
        inv1_type = 'TORSION' if inv1 in TORSION_INVARIANTS else 'NON_TORSION'
        inv2_type = 'TORSION' if inv2 in TORSION_INVARIANTS else 'NON_TORSION'
        
        plot_type = 'STATS_ONLY'
        if inv1 != inv2:
            if inv1_type == 'TORSION' and inv2_type == 'TORSION':
                plot_type = '3D_HEATMAP'
            elif inv1_type == 'TORSION' or inv2_type == 'TORSION':
                plot_type = '1D_HISTO'

        show_style = {'display': 'block'}
        hide_style = {'display': 'none'}

        # Filter Dropdown Options
        inv1_options = [{'label': INVARIANT_SHORTHAND.get(i, i), 'value': i} for i in INVARIANT_ORDER]
        inv2_options = inv1_options.copy()
        if inv1:
            inv2_options = [opt for opt in inv2_options if opt['value'] != inv1]
        if inv2:
            inv1_options = [opt for opt in inv1_options if opt['value'] != inv2]
        
        vis_options_style = show_style
        map_style = show_style
        scale_style = show_style
        x_lim_style = show_style
        y_lim_style = show_style

        if plot_type == 'STATS_ONLY':
            vis_options_style = hide_style
        
        elif plot_type == '1D_HISTO':
            map_style = hide_style
            scale_style = show_style

        elif plot_type == '3D_HEATMAP':
            pass

        return vis_options_style, x_lim_style, y_lim_style, map_style, scale_style, \
               inv1_options, inv2_options

    @app.callback(
        Output('xaxis-min-input', 'value', allow_duplicate=True),
        Output('xaxis-max-input', 'value', allow_duplicate=True),
        Output('yaxis-min-input', 'value', allow_duplicate=True),
        Output('yaxis-max-input', 'value', allow_duplicate=True),
        Input('inv1-dropdown', 'value'),
        Input('inv2-dropdown', 'value'),
        prevent_initial_call=True
    )
    def set_default_axis_limits(inv1, inv2):
        defaults = {
            'tau_NA': [-180, 180], 
            'tau_AC': [-180, 180], 
            'tau_CN': [-180, 180], 
            'angle_N': [0, 360],
            'angle_A': [0, 360],
            'angle_C': [0, 360],
            'length_CN': [1, 2],
            'length_NA': [1, 2],
            'length_AC': [1, 2],
        }
        
        x_min, x_max = defaults.get(inv1, [no_update, no_update])
        y_min, y_max = defaults.get(inv2, [no_update, no_update])
        
        return x_min, x_max, y_min, y_max

    @app.callback(
        Output('confirm-clear-modal', 'is_open'), Output('last-clicked-panel-store', 'data'),
        Input({'type': 'clear-button', 'index': ALL}, 'n_clicks'),
        State('confirm-clear-modal', 'is_open'), prevent_initial_call=True
    )
    def open_clear_modal(clear_clicks, is_open):
        triggered_id_dict = ctx.triggered_id;
        if not triggered_id_dict or is_open or not any(c for c in clear_clicks if c is not None): return no_update, no_update;
        try:
            if isinstance(triggered_id_dict, dict) and 'index' in triggered_id_dict: panel_index = triggered_id_dict['index'];
            elif 'prop_id' in triggered_id_dict: prop_id_str = triggered_id_dict['prop_id'].split('.')[0]; parsed_id = json.loads(prop_id_str.replace("'", '"')); panel_index = parsed_id['index'];
            else: return no_update, no_update;
            return True, panel_index;
        except Exception as e: print(f"Error parsing clear triggered_id: {triggered_id_dict} - {e}"); return no_update, no_update;

    @app.callback(
        Output('panel-states-store', 'data', allow_duplicate=True), Output('confirm-clear-modal', 'is_open', allow_duplicate=True),
        Output('status-message-store', 'data', allow_duplicate=True),
        Input('confirm-clear-button', 'n_clicks'), Input('cancel-clear-button', 'n_clicks'),
        State('last-clicked-panel-store', 'data'), State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def handle_clear_confirmation(confirm_clicks, cancel_clicks, panel_index, panel_states_json):
        button_id = ctx.triggered_id;
        if not button_id or panel_index is None: return no_update, no_update, no_update;
        panel_states = json.loads(panel_states_json or '{}');
        if button_id == 'confirm-clear-button':
            if str(panel_index) in panel_states: del panel_states[str(panel_index)]; return json.dumps(panel_states), False, f"Panel {panel_index + 1} cleared.";
        return no_update, False, no_update;

    @app.callback(
        Output('panel-states-store', 'data', allow_duplicate=True),
        Input({'type': 'toggle-view-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def toggle_panel_view(toggle_clicks, panel_states_json):
        triggered_id_dict = ctx.triggered_id
        if not triggered_id_dict or not any(c for c in toggle_clicks if c is not None):
            return no_update

        try:
            if isinstance(triggered_id_dict, dict) and 'index' in triggered_id_dict:
                panel_index = triggered_id_dict['index']
            elif 'prop_id' in triggered_id_dict:
                prop_id_str = triggered_id_dict['prop_id'].split('.')[0]
                parsed_id = json.loads(prop_id_str.replace("'", '"'))
                panel_index = parsed_id['index']
            else:
                return no_update
        except Exception as e:
            print(f"Error parsing toggle triggered_id: {triggered_id_dict} - {e}")
            return no_update
        
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(panel_index))
        
        if not state or 'view' not in state:
            return no_update
            
        if state['view'] == 'graph':
            state['view'] = 'stats'
        else:
            state['view'] = 'graph'
            
        panel_states[str(panel_index)] = state
        return json.dumps(panel_states)

    @app.callback(
        Output('focus-modal', 'is_open'), Output('focus-modal-header-title', 'children'),
        Output('focus-modal-body', 'children'), Output('last-clicked-panel-store', 'data', allow_duplicate=True),
        Input({'type': 'focus-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        State('sci-notation-store', 'data'),
        prevent_initial_call=True
    )
    def open_focus_modal(focus_clicks, panel_states_json, sci_notation_pref):
        triggered_id_dict = ctx.triggered_id;
        if not triggered_id_dict or not any(c for c in focus_clicks if c is not None): 
            return no_update, no_update, no_update, no_update;
        
        try:
            if isinstance(triggered_id_dict, dict) and 'index' in triggered_id_dict: panel_index = triggered_id_dict['index'];
            elif 'prop_id' in triggered_id_dict: prop_id_str = triggered_id_dict['prop_id'].split('.')[0]; parsed_id = json.loads(prop_id_str.replace("'", '"')); panel_index = parsed_id['index'];
            else: return no_update, no_update, no_update, no_update;
        except Exception as e: print(f"Error parsing focus triggered_id: {triggered_id_dict} - {e}"); return no_update, no_update, no_update, no_update;

        panel_states = json.loads(panel_states_json or '{}'); state = panel_states.get(str(panel_index));
        if not state: return no_update, no_update, no_update, no_update
        
        job_type = state.get('job_type'); modal_title = state.get('title', 'Focus View');
        current_view = state.get('view')
        
        log_scale = state.get('log_scale', True)
        colormap = state.get('colormap', 'Custom Rainbow')
        
        try:
            if current_view == 'graph':
                fig = None;
                if job_type == '3D_HEATMAP': 
                    fig = create_3D_figure(state.get('figure_data',{}), '', state.get('uirevision_key',''), log_scale, colormap, state.get('inv1'), state.get('inv2'), state.get('x_lims'), state.get('y_lims'));
                elif job_type == '1D_HISTO_VS_STATS': 
                    fig = create_1D_histo_figure(state.get('figure_data_histo',{}), '', state.get('inv1'), log_scale);
                elif job_type == '1D_STATS_VS_HISTO': 
                    fig = create_1D_histo_figure(state.get('figure_data_histo',{}), '', state.get('inv2'), log_scale);
                
                if not fig: return no_update, no_update, no_update, no_update;
                modal_body_content = dcc.Graph(figure=fig, style={'height': '100%'});
                return True, modal_title, modal_body_content, panel_index;

            elif current_view == 'stats' or job_type == '1D_STATS_VS_STATS':
                stats_table = build_full_stats_table(state, use_sci_notation=sci_notation_pref)
                modal_body_content = stats_table
                return True, modal_title, modal_body_content, panel_index;

            return no_update, no_update, no_update, no_update;
        except Exception as e: 
            print(f"Error creating focus figure or content: {e}"); import traceback; traceback.print_exc(); 
            return True, modal_title, dbc.Alert(f"Error generating focus view: {e}", color="danger"), panel_index;

    @app.callback(
        Output('status-indicator', 'children'), Output('status-indicator', 'style'),
        Output('status-clear-interval', 'disabled'), Input('status-message-store', 'data'),
        State('status-indicator', 'style')
    )
    def update_status_indicator(message, style):
        if not message: style['opacity'] = 0; return "", style, True;
        style['opacity'] = 1; return message, style, False;

    @app.callback(
        Output('status-message-store', 'data', allow_duplicate=True),
        Input('status-clear-interval', 'n_intervals'), prevent_initial_call=True
    )
    def clear_status_message(n_intervals): return "";

    @app.callback(
        Output("download-html", "data"), 
        Input({'type': 'download-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        State('sci-notation-store', 'data'),
        prevent_initial_call=True
    )
    def download_graph_html(download_clicks, panel_states_json, sci_notation_pref):
        triggered_id_dict = ctx.triggered_id;
        if not triggered_id_dict or not any(c for c in download_clicks if c is not None): 
            return no_update;
        
        try:
            if isinstance(triggered_id_dict, dict) and 'index' in triggered_id_dict: panel_index = triggered_id_dict['index'];
            elif 'prop_id' in triggered_id_dict: prop_id_str = triggered_id_dict['prop_id'].split('.')[0]; parsed_id = json.loads(prop_id_str.replace("'", '"')); panel_index = parsed_id['index'];
            else: return no_update;
        except Exception as e: print(f"Error parsing download triggered_id: {triggered_id_dict} - {e}"); return no_update;
        
        panel_states = json.loads(panel_states_json or '{}'); state = panel_states.get(str(panel_index));
        if not state: return no_update
        
        job_type = state.get('job_type');
        current_view = state.get('view')
        title_str = state.get('title', 'panel_data').replace(' ', '_').replace('+', '').replace('(', '').replace(')', '').replace(':', '').replace('|', '_').replace('-', '')

        log_scale = state.get('log_scale', True)
        colormap = state.get('colormap', 'Custom Rainbow')

        try:
            if current_view == 'graph':
                fig = None;
                if job_type == '3D_HEATMAP': 
                    fig = create_3D_figure(state.get('figure_data',{}), state.get('title', ''), state.get('uirevision_key',''), log_scale, colormap, state.get('inv1'), state.get('inv2'), state.get('x_lims'), state.get('y_lims'));
                elif job_type == '1D_HISTO_VS_STATS': 
                    fig = create_1D_histo_figure(state.get('figure_data_histo',{}), state.get('title', ''), state.get('inv1'), log_scale);
                elif job_type == '1D_STATS_VS_HISTO': 
                    fig = create_1D_histo_figure(state.get('figure_data_histo',{}), state.get('title', ''), state.get('inv2'), log_scale);
                
                if fig:
                    filename = f"{title_str}_graph.html";
                    return dict(content=pio.to_html(fig, full_html=True), filename=filename);
            
            elif current_view == 'stats' or job_type == '1D_STATS_VS_STATS':
                if not state.get('full_v8_stats'): return no_update
                csv_string = create_stats_csv(state, use_sci_notation=sci_notation_pref) 
                filename = f"{title_str}_stats.csv";
                return dict(content=csv_string, filename=filename, type="text/csv", base64=False)

            return no_update;
        except Exception as e: 
            print(f"Error creating download file: {e}"); 
            import traceback; traceback.print_exc()
            return no_update;