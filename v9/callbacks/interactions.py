import json
import plotly.io as pio
from dash import dcc, html, Input, Output, State, no_update, ctx, ALL, MATCH
import dash_bootstrap_components as dbc
from flask import request as flask_request
from .rendering import create_3D_figure, create_1D_histo_figure, build_full_stats_table, format_stat_value
from ..constants import (
    INVARIANT_SHORTHAND, TORSION_INVARIANTS, INVARIANT_ORDER,
    NON_TORSION_INVARIANTS, AMINO_ACID_NAMES, MAX_GRAPHS, BASE_PATH, PLOTLY_COLORSCALES
)
import io
import csv
import numpy as np
import urllib.parse
import re
import time
import traceback

# --- V8 Encoding System ---
SHORTCODE_MAP = {
    'tau_NA': 'p', 'tau_AC': 'y', 'tau_CN': 'w',
    'angle_N': 'a', 'angle_A': 'b', 'angle_C': 'c',
    'length_NA': 'l', 'length_AC': 'm', 'length_CN': 'n'
}
REVERSE_SHORTCODE_MAP = {v: k for k, v in SHORTCODE_MAP.items()}


def create_stats_csv(panel_state: dict, use_sci_notation: bool = False) -> str:
    stats_data = panel_state.get('full_v8_stats')
    if not stats_data: return ""
    
    inv1 = panel_state.get('inv1', 'X')
    inv2 = panel_state.get('inv2', 'Y')
    inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1)
    inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2)

    stat_order = [
        ('population', 'Population'),
        ('mean_x', f'Mean ({inv1_label})'), ('mean_y', f'Mean ({inv2_label})'),
        ('variance_x', f'Variance ({inv1_label})'), ('variance_y', f'Variance ({inv2_label})'),
        ('freq_at_mean_x', f'Freq. at Mean ({inv1_label})'), ('freq_at_mean_y', f'Freq. at Mean ({inv2_label})'),
        ('median_x', f'Median ({inv1_label})'), ('median_y', f'Median ({inv2_label})'),
        ('min_x', f'Min ({inv1_label})'), ('min_y', f'Min ({inv2_label})'),
        ('max_x', f'Max ({inv1_label})'), ('max_y', f'Max ({inv2_label})'),
        ('covariance', 'Covariance'), ('pearson_correlation', "Pearson's (ρ)"),
        ('peak_x', f'Peak ({inv1_label})'), ('peak_y', f'Peak ({inv2_label})'),
        ('peak_freq', 'Peak Frequency'),
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Statistic', 'Value'])
    for key, friendly_name in stat_order:
        value = stats_data.get(key)
        if value is None: value_str = "N/A"
        elif isinstance(value, (int, np.integer)): value_str = f"{value:,}"
        elif isinstance(value, (float, np.floating)):
            prec = 4 if key == 'pearson_correlation' else 3
            value_str = format_stat_value(value, use_sci_notation, precision=prec)
        else: value_str = str(value)
        writer.writerow([friendly_name, value_str])
    return output.getvalue()


def register_interaction_callbacks(app):
    # =====================================================================
    # FIX: IDEMPOTENCY GUARD
    # Prevents "Duplicate Callback Outputs" and "Overlapping Wildcard" 
    # errors if Python's import system executes this function twice.
    # =====================================================================
    if getattr(app, '_v8_callbacks_registered', False):
        print("[V8 DEBUG] Callbacks already registered for this app! Skipping duplicate registration.")
        return
    app._v8_callbacks_registered = True

    print("[V8 DEBUG] Registering interaction callbacks...")

    # =====================================================================
    # PRIMARY CALLBACKS DEFINED FIRST
    # =====================================================================

    @app.callback(
        Output('v8-panel-states-store', 'data'), # Primary output (no allow_duplicate)
        Input('url', 'search'),
        State('v8-panel-states-store', 'data')
    )
    def load_state_from_url(search, current_store_json):
        print(f"\n[V8 DEBUG] === load_state_from_url triggered ===")
        print(f"[V8 DEBUG] URL Search Param: '{search}'")
        
        # Always start fresh on page load/reload — ignore stale session data.
        # Only preserve state if a URL query string provides panels to restore.
        fallback_state = '{}'
        
        if not search: 
            print("[V8 DEBUG] No search string. Starting with blank state.")
            return fallback_state

        try:
            q = urllib.parse.parse_qs(urllib.parse.urlparse(search).query)
            if 'q' not in q: 
                print("[V8 DEBUG] Search string found, but no 'q' parameter. Yielding fallback state.")
                return fallback_state
            
            segments = q['q'][0].split('_')
            states = json.loads(fallback_state)
            updated = False
            
            from .data_fetching import fetch_v8_data, get_plot_key_for_query
            import sqlite3; from ..constants import DB_PATH
            
            print(f"[V8 DEBUG] Parsing Q8 URL Parameter segments: {segments}")
            with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
                for i, seg in enumerate(segments):
                    if i >= 6: break
                    if not seg: continue
                    parts = seg.split('~')
                    core = parts[0]
                    if len(core) < 7:
                        print(f"[V8 DEBUG] Segment {i} too short ({len(core)} chars), skipping.")
                        continue
                    res1 = core[0]; res2 = core[1]
                    try: offset = int(core[2])
                    except: offset = 0
                    try: focus_raw = int(core[3])
                    except: focus_raw = 1
                    if offset == 0:
                        pos = 0
                        if res1 != res2:
                            print(f"[V8 DEBUG] Warning: step=0 but res1={res1} != res2={res2}. Ignoring res2.")
                    else:
                        pos = 0 if focus_raw == 1 else 1
                    inv1 = REVERSE_SHORTCODE_MAP.get(core[4], 'tau_NA')
                    inv2 = REVERSE_SHORTCODE_MAP.get(core[5], 'tau_AC')
                    view = 'stats' if core[6] == 's' else 'graph'

                    log_scale = True; colormap = 'Custom Rainbow'
                    x_lims = [None, None]; y_lims = [None, None]
                    if len(parts) > 1:
                        vis = parts[1].split(',')
                        if len(vis) == 5 and len(vis[0]) >= 2:
                            try: colormap = PLOTLY_COLORSCALES[int(vis[0][0])]
                            except (ValueError, IndexError): pass
                            log_scale = vis[0][1] == '1'
                            def _parse(v):
                                try: return float(v) if v != 'N' else None
                                except ValueError: return None
                            x_lims = [_parse(vis[1]), _parse(vis[2])]
                            y_lims = [_parse(vis[3]), _parse(vis[4])]

                    try:
                        plot_key = get_plot_key_for_query(inv1, inv2, offset, res1, res2, pos)
                        data = fetch_v8_data(conn, plot_key)

                        inv1_l = INVARIANT_SHORTHAND.get(inv1, inv1); inv2_l = INVARIANT_SHORTHAND.get(inv2, inv2)
                        title = f"{inv1_l} vs {inv2_l} (Residue {res1})" if offset==0 else f"Focus: {res1} ({inv1_l} vs {inv2_l}) | Context: {res2} at +{offset}"

                        new_state = {
                            'title': title, 'inv1': inv1, 'inv2': inv2, 'offset': offset, 'res1': res1, 'res2': res2, 'pos': pos,
                            'x_lims': x_lims, 'y_lims': y_lims, 'uirevision_key': str(time.time()),
                            'full_v8_stats': data['stats_v8'], 'log_scale': log_scale, 'colormap': colormap, 'view': view
                        }

                        if data['job_type_v8'] == '3D_VIZ':
                            new_state['job_type'] = '3D_HEATMAP'
                            new_state['figure_data'] = data['figure_data_3d']
                            new_state['stats'] = {'population': data['stats_v8'].get('population'), 'peak_x': data['stats_v8'].get('peak_x'), 'peak_y': data['stats_v8'].get('peak_y'), 'peak_freq': data['stats_v8'].get('peak_freq')}
                        elif data['job_type_v8'] == 'STATS_AND_HISTO':
                            is_t = inv1 in TORSION_INVARIANTS
                            new_state['job_type'] = '1D_HISTO_VS_STATS' if is_t else '1D_STATS_VS_HISTO'
                            new_state['figure_data_histo'] = data['figure_data_histo_x'] if is_t else data['figure_data_histo_y']
                        elif data['job_type_v8'] == 'STATS_ONLY':
                            new_state['job_type'] = '1D_STATS_VS_STATS'

                        states[str(i)] = new_state; updated = True
                    except Exception as e: print(f"[V8 DEBUG] URL Load Error V8 {i}: {e}")
            
            if updated: 
                print("[V8 DEBUG] URL successfully interpreted, returning updated store.")
                return json.dumps(states)
            return fallback_state
        except Exception as e: 
            print(f"[V8 DEBUG] URL Parse Exception:\n{traceback.format_exc()}")
            return fallback_state

    @app.callback(
        Output('status-message-store', 'data'), # Primary output (no allow_duplicate)
        Input('status-clear-interval', 'n_intervals'), 
        prevent_initial_call=True
    )
    def clear_status(n): 
        return ""

    # =====================================================================
    # SHARE URL CALLBACKS
    # =====================================================================

    @app.callback(
        Output('share-url-box', 'value'),
        Input('v8-panel-states-store', 'data')
    )
    def update_share_url(panel_states_json):
        """Generates the full shareable URL based on current panel state."""
        if not panel_states_json:
            return ""
        
        panel_states = json.loads(panel_states_json)
        if not panel_states: return ""
        encoded_parts = []
        
        max_idx = max([int(k) for k in panel_states.keys()]) if panel_states else -1
        
        for i in range(max_idx + 1):
            if str(i) not in panel_states:
                encoded_parts.append("")
                continue
                
            state = panel_states.get(str(i)) or {}
            res1 = state.get('res1', 'A')
            res2 = state.get('res2', 'A')
            offset = state.get('offset', 0)
            pos = state.get('pos', 0)

            inv1 = state.get('inv1', 'tau_NA')
            inv2 = state.get('inv2', 'tau_AC')
            view = state.get('view', 'graph')
            log_scale = state.get('log_scale', True)
            colormap = state.get('colormap', 'Custom Rainbow')
            x_lims = state.get('x_lims', [None, None])
            y_lims = state.get('y_lims', [None, None])

            c1 = SHORTCODE_MAP.get(inv1, 'p')
            c2 = SHORTCODE_MAP.get(inv2, 'y')
            v_char = 'g' if view == 'graph' else 's'
            focus_char = '0' if offset == 0 else ('1' if pos == 0 else '2')

            is_default_vis = (
                log_scale is True and
                colormap == 'Custom Rainbow' and
                x_lims[0] is None and x_lims[1] is None and
                y_lims[0] is None and y_lims[1] is None
            )
            if is_default_vis:
                vis_suffix = ''
            else:
                try: cmap_idx = PLOTLY_COLORSCALES.index(colormap)
                except ValueError: cmap_idx = 0
                scale_char = '1' if log_scale else '0'
                def _fmt(v): return str(v) if v is not None else 'N'
                vis_suffix = f"~{cmap_idx}{scale_char},{_fmt(x_lims[0])},{_fmt(x_lims[1])},{_fmt(y_lims[0])},{_fmt(y_lims[1])}"

            segment = f"{res1}{res2}{offset}{focus_char}{c1}{c2}{v_char}{vis_suffix}"
            encoded_parts.append(segment)
            
        q_string = "_".join(encoded_parts)
        if not q_string: return ""
        
        host = flask_request.host_url.rstrip('/')
        return f"{host}{BASE_PATH}/v8/?q={q_string}"

    # Clientside callback: clicking the share link copies the URL to clipboard
    app.clientside_callback(
        """
        function(n_clicks, url_value) {
            if (!n_clicks || !url_value) return window.dash_clientside.no_update;
            navigator.clipboard.writeText(url_value).then(function() {
                var el = document.getElementById('share-layout-link');
                if (el) {
                    var orig = el.innerText;
                    el.innerText = '✓ Copied!';
                    setTimeout(function() { el.innerHTML = '<i class="bi bi-link-45deg me-1"></i>Share Layout'; }, 1500);
                }
            });
            return window.dash_clientside.no_update;
        }
        """,
        Output('share-layout-link', 'style'),
        Input('share-layout-link', 'n_clicks'),
        State('share-url-box', 'value'),
        prevent_initial_call=True
    )

    # =====================================================================
    # REST OF CALLBACKS
    # =====================================================================

    app.clientside_callback(
        """
        function(menu_clicks, config_clicks, placeholder_clicks, close_clicks, generate_clicks, current_class) {
            const triggered = dash_clientside.callback_context.triggered;
            if (!triggered || triggered.length === 0) return window.dash_clientside.no_update;

            // Only operate modal logic if screen ratio is < 17/24
            const isMobile = window.matchMedia("(max-aspect-ratio: 17/24)").matches;
            if (!isMobile) {
                // If we aren't changing the class, return no_update to prevent React from flashing the DOM node
                if (current_class === "left-panel") return window.dash_clientside.no_update;
                return "left-panel";
            }

            const prop_id = triggered[0].prop_id;
            let is_open = (current_class && current_class.includes('mobile-open'));
            let target_open = is_open;

            if (prop_id.includes("mobile-menu-toggle") || (prop_id.includes("config-button") && triggered[0].value) || (prop_id.includes("placeholder-button") && triggered[0].value)) {
                target_open = true;
            } else if (prop_id.includes("mobile-menu-close") || prop_id.includes("generate-graph-button")) {
                target_open = false;
            }

            // Prevent React from gratuitously re-rendering the DOM if the state isn't changing
            if (target_open === is_open) return window.dash_clientside.no_update;

            return target_open ? "left-panel mobile-open" : "left-panel";
        }
        """,
        Output('config-left-panel', 'className'),
        Input('mobile-menu-toggle', 'n_clicks'),
        Input({'type': 'config-button', 'index': ALL}, 'n_clicks'),
        Input({'type': 'placeholder-button', 'index': ALL}, 'n_clicks'),
        Input('mobile-menu-close', 'n_clicks'),
        Input('generate-graph-button', 'n_clicks'),
        State('config-left-panel', 'className'),
        prevent_initial_call=True
    )

    @app.callback(
        Output('v8-sci-notation-store', 'data'),
        Input('sci-notation-switch', 'value')
    )
    def update_sci_notation_store(switch_value):
        print(f"[V8 DEBUG] update_sci_notation_store called: {switch_value}")
        return switch_value

    @app.callback(
        Output('xaxis-limit-label', 'children'),
        Output('yaxis-limit-label', 'children'),
        Input('inv1-dropdown', 'value'), Input('inv2-dropdown', 'value')
    )
    def update_axis_labels(inv1, inv2):
        inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1); inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2);
        return f"{inv1_label}-axis limits", f"{inv2_label}-axis limits"

    @app.callback(
        Output('active-panel-store', 'data'), Output('active-panel-display', 'children'),
        Output('inv1-dropdown', 'value'), Output('inv2-dropdown', 'value'),
        Output('offset-dropdown', 'value'), 
        Output('res1-dropdown', 'value'), Output('res2-dropdown', 'value'),
        Output('pos-0-checkbox', 'value'), Output('pos-1-checkbox', 'value'),
        Output('xaxis-min-input', 'value'), Output('xaxis-max-input', 'value'), 
        Output('yaxis-min-input', 'value'), Output('yaxis-max-input', 'value'),
        Output('scale-switch', 'value'), Output('colormap-dropdown', 'value'),
        Output('sci-notation-switch', 'value'),
        Input({'type': 'config-button', 'index': ALL}, 'n_clicks'),
        Input({'type': 'placeholder-button', 'index': ALL}, 'n_clicks'),
        State('v8-panel-states-store', 'data'),
        State('v8-sci-notation-store', 'data'),
        prevent_initial_call=True
    )
    def update_active_panel(config_clicks, placeholder_clicks, panel_states_json, sci_notation_pref):
        print("\n[V8 DEBUG] --- update_active_panel triggered ---")
        triggered_id_dict = ctx.triggered_id
        
        default_return = (
            0, "Configure Panel 1", 'tau_NA', 'tau_AC', 0, 'A', 'A', 
            True, False, None, None, None, None, True, 'Custom Rainbow', sci_notation_pref or False
        )
        if not triggered_id_dict:
            print("[V8 DEBUG] No triggered ID found.")
            if not any(c for c in config_clicks if c) and not any(p for p in placeholder_clicks if p): 
                return default_return
            else: 
                return no_update
        
        try:
            if isinstance(triggered_id_dict, dict) and 'index' in triggered_id_dict: 
                active_panel_index = triggered_id_dict['index']
            elif 'prop_id' in triggered_id_dict: 
                parsed_id = json.loads(triggered_id_dict['prop_id'].split('.')[0].replace("'", '"'))
                active_panel_index = parsed_id['index']
            else: 
                return no_update
        except Exception as e: 
            print(f"[V8 DEBUG] Exception while parsing triggered_id: {e}")
            return no_update
        
        print(f"[V8 DEBUG] Setting active panel index to: {active_panel_index}")
        
        panel_states = json.loads(panel_states_json or '{}') 
        state = panel_states.get(str(active_panel_index))
        
        inv1 = state.get('inv1', 'tau_NA') if state else 'tau_NA'; 
        inv2 = state.get('inv2', 'tau_AC') if state else 'tau_AC';
        offset = state.get('offset', 0) if state else 0; 
        res1 = state.get('res1', 'A') if state else 'A'; 
        res2 = state.get('res2', 'A') if state else 'A';
        pos = state.get('pos', 0) if state else 0;
        x_lims = state.get('x_lims', [None, None]) if state else [None, None]; 
        y_lims = state.get('y_lims', [None, None]) if state else [None, None];
        log_scale = state.get('log_scale', True) if state else True
        colormap = state.get('colormap', 'Custom Rainbow') if state else 'Custom Rainbow'

        return (
            active_panel_index, f"Configure Panel {active_panel_index + 1}", 
            inv1, inv2, offset, res1, res2, 
            (pos == 0), (pos == 1),
            x_lims[0], x_lims[1], y_lims[0], y_lims[1],
            log_scale, colormap, sci_notation_pref or False
        )

    @app.callback(
        Output('pos-0-checkbox', 'value', allow_duplicate=True),
        Output('pos-1-checkbox', 'value', allow_duplicate=True),
        Input('pos-0-checkbox', 'value'), Input('pos-1-checkbox', 'value'),
        State('offset-dropdown', 'value'), prevent_initial_call=True
    )
    def update_checkbox_exclusivity(pos0_val, pos1_val, offset):
        if offset == 0: return True, False
        if ctx.triggered_id == 'pos-0-checkbox': return pos0_val, not pos0_val
        elif ctx.triggered_id == 'pos-1-checkbox': return not pos1_val, pos1_val
        return no_update, no_update

    @app.callback(
        Output('res1-container', 'style'), Output('res2-container', 'style'),
        Output('pos-0-checkbox', 'style'), Output('pos-0-checkbox', 'disabled'),
        Output('pos-1-checkbox', 'style'), Output('visual-options-container', 'style'),
        Output('xaxis-limit-container', 'style'), Output('yaxis-limit-container', 'style'),
        Output('colormap-container', 'style'), Output('scale-switch-container', 'style'),
        Output('inv1-dropdown', 'options'), Output('inv2-dropdown', 'options'),
        Input('offset-dropdown', 'value'), Input('inv1-dropdown', 'value'), Input('inv2-dropdown', 'value')
    )
    def manage_config_panel_layout(offset, inv1, inv2):
        inv1_type = 'TORSION' if inv1 in TORSION_INVARIANTS else 'NON_TORSION'
        inv2_type = 'TORSION' if inv2 in TORSION_INVARIANTS else 'NON_TORSION'
        
        plot_type = 'STATS_ONLY'
        if inv1 != inv2:
            if inv1_type == 'TORSION' and inv2_type == 'TORSION': plot_type = '3D_HEATMAP'
            elif inv1_type == 'TORSION' or inv2_type == 'TORSION': plot_type = '1D_HISTO'
            
        hide = {'display': 'none'}; show = {'display': 'block'};
        res1_s, res2_s, pos0_s, pos0_d, pos1_s = show, show, show, False, show
        if offset == 0: res2_s = hide; pos0_d = True; pos1_s = hide;
        
        inv1_opt = [{'label': INVARIANT_SHORTHAND.get(i, i), 'value': i} for i in INVARIANT_ORDER]
        inv2_opt = inv1_opt.copy()
        if inv1: inv2_opt = [o for o in inv2_opt if o['value'] != inv1]
        if inv2: inv1_opt = [o for o in inv1_opt if o['value'] != inv2]
        
        if plot_type == 'STATS_ONLY':
            return res1_s, res2_s, pos0_s, pos0_d, pos1_s, hide, no_update, no_update, no_update, no_update, inv1_opt, inv2_opt
        elif plot_type == '1D_HISTO':
            x_s, y_s = show, hide; map_s, scale_s = hide, show
            if inv2_type == 'TORSION': x_s, y_s = y_s, x_s
            return res1_s, res2_s, pos0_s, pos0_d, pos1_s, show, x_s, y_s, map_s, scale_s, inv1_opt, inv2_opt
        return res1_s, res2_s, pos0_s, pos0_d, pos1_s, show, show, show, show, show, inv1_opt, inv2_opt

    @app.callback(
        Output('xaxis-min-input', 'value', allow_duplicate=True), Output('xaxis-max-input', 'value', allow_duplicate=True),
        Output('yaxis-min-input', 'value', allow_duplicate=True), Output('yaxis-max-input', 'value', allow_duplicate=True),
        Input('inv1-dropdown', 'value'), Input('inv2-dropdown', 'value'), prevent_initial_call=True
    )
    def set_default_axis_limits(inv1, inv2):
        defaults = {
            'tau_NA': [-180, 180], 'tau_AC': [-180, 180], 'tau_CN': [-90, 270],
            'angle_N': [0, 360], 'angle_A': [0, 360], 'angle_C': [0, 360],
            'length_CN': [1, 2], 'length_NA': [1, 2], 'length_AC': [1, 2],
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
        print("\n[V8 DEBUG] --- open_clear_modal triggered ---")
        if not ctx.triggered_id or is_open or not any(c for c in clear_clicks if c): return no_update, no_update
        try:
            pid = ctx.triggered_id.get('index') if isinstance(ctx.triggered_id, dict) else json.loads(ctx.triggered_id.split('.')[0].replace("'", '"'))['index']
            print(f"[V8 DEBUG] Opening clear modal for panel: {pid}")
            return True, pid
        except: return no_update, no_update

    @app.callback(
        Output('v8-panel-states-store', 'data', allow_duplicate=True), Output('confirm-clear-modal', 'is_open', allow_duplicate=True),
        Output('status-message-store', 'data', allow_duplicate=True),
        Input('confirm-clear-button', 'n_clicks'), Input('cancel-clear-button', 'n_clicks'),
        State('last-clicked-panel-store', 'data'), State('v8-panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def handle_clear(confirm, cancel, panel_index, panel_states_json):
        if ctx.triggered_id == 'confirm-clear-button' and panel_index is not None:
            print(f"\n[V8 DEBUG] Clearing panel {panel_index}")
            states = json.loads(panel_states_json or '{}')
            if str(panel_index) in states: 
                del states[str(panel_index)]
                return json.dumps(states), False, f"Panel {panel_index + 1} cleared."
        return no_update, False, no_update

    @app.callback(
        Output('v8-panel-states-store', 'data', allow_duplicate=True),
        Input({'type': 'toggle-view-button', 'index': ALL}, 'n_clicks'),
        State('v8-panel-states-store', 'data'), prevent_initial_call=True
    )
    def toggle_panel_view(toggle_clicks, panel_states_json):
        if not ctx.triggered_id or not any(c for c in toggle_clicks if c): return no_update
        try:
            idx = ctx.triggered_id.get('index') if isinstance(ctx.triggered_id, dict) else json.loads(ctx.triggered_id.split('.')[0].replace("'", '"'))['index']
            print(f"\n[V8 DEBUG] Toggling view for panel {idx}")
            states = json.loads(panel_states_json or '{}')
            if str(idx) in states:
                states[str(idx)]['view'] = 'stats' if states[str(idx)].get('view') == 'graph' else 'graph'
                return json.dumps(states)
        except Exception as e: 
            print(f"[V8 DEBUG] Toggle Error: {e}")
            pass
        return no_update

    @app.callback(
        Output('focus-modal', 'is_open'), Output('focus-modal-header-title', 'children'),
        Output('focus-modal-body', 'children'), Output('last-clicked-panel-store', 'data', allow_duplicate=True),
        Input({'type': 'focus-button', 'index': ALL}, 'n_clicks'),
        State('v8-panel-states-store', 'data'), State('v8-sci-notation-store', 'data'),
        prevent_initial_call=True
    )
    def open_focus_modal(focus_clicks, panel_states_json, sci_pref):
        if not ctx.triggered_id or not any(c for c in focus_clicks if c): return no_update, no_update, no_update, no_update
        try:
            idx = ctx.triggered_id.get('index') if isinstance(ctx.triggered_id, dict) else json.loads(ctx.triggered_id.split('.')[0].replace("'", '"'))['index']
            print(f"\n[V8 DEBUG] Opening focus modal for panel {idx}")
            state = json.loads(panel_states_json or '{}').get(str(idx))
            if not state: return no_update, no_update, no_update, no_update
            
            job = state.get('job_type'); title = state.get('title', 'Focus View'); view = state.get('view')
            
            if view == 'graph':
                fig = None
                if job == '3D_HEATMAP': 
                    fig = create_3D_figure(state.get('figure_data',{}), '', state.get('uirevision_key',''), state.get('log_scale',True), state.get('colormap','Custom Rainbow'), state.get('inv1'), state.get('inv2'), state.get('x_lims'), state.get('y_lims'))
                elif job in ['1D_HISTO_VS_STATS', '1D_STATS_VS_HISTO']:
                    inv = state.get('inv1') if job == '1D_HISTO_VS_STATS' else state.get('inv2')
                    fig = create_1D_histo_figure(state.get('figure_data_histo',{}), '', inv, state.get('log_scale',True))
                if fig: return True, title, dcc.Graph(figure=fig, style={'height': '100%'}), idx
            
            elif view == 'stats' or job == '1D_STATS_VS_STATS':
                return True, title, build_full_stats_table(state, use_sci_notation=sci_pref), idx

        except Exception as e: 
            print(f"[V8 DEBUG] Focus Error: {e}")
            return True, title, dbc.Alert(f"Error: {e}", color="danger"), idx
        return no_update, no_update, no_update, no_update

    @app.callback(
        Output('status-indicator', 'children'), Output('status-indicator', 'style'),
        Output('status-clear-interval', 'disabled'), Input('status-message-store', 'data'),
        State('status-indicator', 'style')
    )
    def update_status(msg, style):
        if not msg: style['opacity'] = 0; return "", style, True
        style['opacity'] = 1; return msg, style, False

    @app.callback(
        Output("download-html", "data"), 
        Input({'type': 'download-button', 'index': ALL}, 'n_clicks'),
        State('v8-panel-states-store', 'data'), State('v8-sci-notation-store', 'data'),
        prevent_initial_call=True
    )
    def download(clicks, states_json, sci_pref):
        if not ctx.triggered_id or not any(c for c in clicks if c): return no_update
        try:
            idx = ctx.triggered_id.get('index') if isinstance(ctx.triggered_id, dict) else json.loads(ctx.triggered_id.split('.')[0].replace("'", '"'))['index']
            state = json.loads(states_json or '{}').get(str(idx))
            if not state: return no_update
            
            title = state.get('title', 'data').replace(' ', '_')
            if state.get('view') == 'graph':
                fig = None
                if state.get('job_type') == '3D_HEATMAP':
                    fig = create_3D_figure(state.get('figure_data',{}), state.get('title',''), '', state.get('log_scale',True), state.get('colormap','Custom Rainbow'), state.get('inv1'), state.get('inv2'), state.get('x_lims'), state.get('y_lims'))
                # ... same logic as focus for other types ...
                if fig: return dict(content=pio.to_html(fig, full_html=True), filename=f"{title}.html")
            else:
                return dict(content=create_stats_csv(state, sci_pref), filename=f"{title}.csv", type="text/csv")
        except: pass
        return no_update

    # --- CORE GRAPH GENERATION CALLBACKS ---
    @app.callback(
        Output('v8-panel-states-store', 'data', allow_duplicate=True),
        Output('status-message-store', 'data', allow_duplicate=True),
        Input('generate-graph-button', 'n_clicks'),
        State('active-panel-store', 'data'),
        State('inv1-dropdown', 'value'), State('inv2-dropdown', 'value'),
        State('offset-dropdown', 'value'),
        State('res1-dropdown', 'value'), State('res2-dropdown', 'value'),
        State('pos-0-checkbox', 'value'),
        State('xaxis-min-input', 'value'), State('xaxis-max-input', 'value'),
        State('yaxis-min-input', 'value'), State('yaxis-max-input', 'value'),
        State('scale-switch', 'value'), State('colormap-dropdown', 'value'),
        State('v8-panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def generate_panel_data(n_clicks, active_panel, inv1, inv2, offset, res1, res2, pos0_val, x_min, x_max, y_min, y_max, log_scale, colormap, states_json):
        print(f"\n[V8 DEBUG] === generate_panel_data triggered ===")
        print(f"[V8 DEBUG] n_clicks: {n_clicks}")
        if not n_clicks: 
            print("[V8 DEBUG] Exiting generate_panel_data: No clicks.")
            return no_update, no_update
        try:
            states = json.loads(states_json or '{}')
            pos = 0 if pos0_val else 1
            print(f"[V8 DEBUG] Target Panel: {active_panel}, Querying DB for: {inv1} vs {inv2}, offset={offset}, res1={res1}, res2={res2}, pos={pos}")
            
            from .data_fetching import fetch_v8_data, get_plot_key_for_query
            import sqlite3; from ..constants import DB_PATH
            
            with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
                plot_key = get_plot_key_for_query(inv1, inv2, offset, res1, res2, pos)
                print(f"[V8 DEBUG] Constructed plot_key: {plot_key}")
                data = fetch_v8_data(conn, plot_key)
                
                if not data:
                    print(f"[V8 DEBUG] WARNING: fetch_v8_data returned None or empty for plot_key {plot_key}")
                    return no_update, f"Error: No data found for {plot_key}"

                print(f"[V8 DEBUG] DB Fetch Success! Job type returned: {data.get('job_type_v8')}")

                inv1_l = INVARIANT_SHORTHAND.get(inv1, inv1); inv2_l = INVARIANT_SHORTHAND.get(inv2, inv2)
                if offset == 0:
                    title = f"{inv1_l} vs {inv2_l} (Residue {res1})"
                else:
                    focus_res = res1 if pos == 0 else res2
                    context_res = res2 if pos == 0 else res1
                    title = f"Focus: {focus_res} ({inv1_l} vs {inv2_l}) | Context: {context_res} at +{offset}"
                
                new_state = {
                    'title': title, 'inv1': inv1, 'inv2': inv2, 'offset': offset, 'res1': res1, 'res2': res2, 'pos': pos,
                    'x_lims': [x_min, x_max], 'y_lims': [y_min, y_max], 'uirevision_key': str(time.time()),
                    'full_v8_stats': data.get('stats_v8', {}), 'log_scale': log_scale, 'colormap': colormap, 'view': 'graph'
                }
                
                if data.get('job_type_v8') == '3D_VIZ':
                    new_state['job_type'] = '3D_HEATMAP'
                    new_state['figure_data'] = data['figure_data_3d']
                    new_state['stats'] = {'population': data['stats_v8'].get('population'), 'peak_x': data['stats_v8'].get('peak_x'), 'peak_y': data['stats_v8'].get('peak_y'), 'peak_freq': data['stats_v8'].get('peak_freq')}
                elif data.get('job_type_v8') == 'STATS_AND_HISTO':
                    is_t = inv1 in TORSION_INVARIANTS
                    new_state['job_type'] = '1D_HISTO_VS_STATS' if is_t else '1D_STATS_VS_HISTO'
                    new_state['figure_data_histo'] = data['figure_data_histo_x'] if is_t else data['figure_data_histo_y']
                elif data.get('job_type_v8') == 'STATS_ONLY':
                    new_state['job_type'] = '1D_STATS_VS_STATS'
                
                states[str(active_panel)] = new_state
                print(f"[V8 DEBUG] Success. Emitting updated state to store.")
                return json.dumps(states), f"Loaded data for Panel {active_panel + 1}"

        except Exception as e:
            print(f"[V8 DEBUG] CRITICAL ERROR IN generate_panel_data:\n{traceback.format_exc()}")
            return no_update, f"Error: {e}"

    # =================================================================
    # FIX: Use explicit indexed Outputs instead of ALL pattern-matching.
    # Dash can silently fail to resolve ALL on Outputs, especially when
    # the target components' children are dynamically replaced. Explicit
    # indexed outputs are always reliably resolved.
    # =================================================================
    @app.callback(
        [Output({'type': 'graph-col', 'index': i}, 'children') for i in range(MAX_GRAPHS)],
        Input('v8-panel-states-store', 'data'),
        State('v8-sci-notation-store', 'data')
    )
    def render_all_panels(panel_states_json, sci_pref):
        print(f"\n[V8 DEBUG] === render_all_panels triggered ===")
        print(f"[V8 DEBUG] MAX_GRAPHS constant evaluates to: {MAX_GRAPHS}")
        
        try:
            states = json.loads(panel_states_json or '{}')
            print(f"[V8 DEBUG] Store decoded. Contains {len(states.keys())} active panels.")
        except Exception as e:
            print(f"[V8 DEBUG] JSON Parse Error in render_all_panels:\n{traceback.format_exc()}")
            states = {}
            
        outputs = []
        for i in range(MAX_GRAPHS):
            try:
                state = states.get(str(i))
                if not state:
                    outputs.append(
                        html.Div(
                            className="placeholder-panel",
                            id={'type': 'placeholder-button', 'index': i},
                            children=[html.I(className="bi bi-plus-lg")]
                        )
                    )
                    continue
                
                print(f"[V8 DEBUG] Rendering content for panel {i}")
                job = state.get('job_type')
                view = state.get('view', 'graph')
                
                if view == 'graph':
                    toggle_icon, toggle_title = "bi bi-table", "Switch to Stats View"
                else:
                    toggle_icon, toggle_title = "bi bi-box", "Switch to Graph View"

                buttons = html.Div(
                    style={'position': 'absolute', 'bottom': '10px', 'right': '10px', 'zIndex': 10, 'display': 'flex', 'gap': '0.25rem'},
                    children=[
                        dbc.Button(html.I(className=toggle_icon), id={'type': 'toggle-view-button', 'index': i}, size="sm", title=toggle_title),
                        dbc.Button(html.I(className="bi bi-arrows-fullscreen"), id={'type': 'focus-button', 'index': i}, size="sm", title="Focus View"),
                        dbc.Button(html.I(className="bi bi-download"), id={'type': 'download-button', 'index': i}, size="sm", title="Download"),
                        dbc.Button(html.I(className="bi bi-gear"), id={'type': 'config-button', 'index': i}, size="sm", title="Configure"),
                        dbc.Button(html.I(className="bi bi-x-lg"), id={'type': 'clear-button', 'index': i}, size="sm", color="danger", title="Clear"),
                    ]
                )
                
                content = None
                if view == 'graph':
                    if job == '3D_HEATMAP':
                        fig = create_3D_figure(state.get('figure_data',{}), state.get('title',''), state.get('uirevision_key',''), state.get('log_scale',True), state.get('colormap','Custom Rainbow'), state.get('inv1'), state.get('inv2'), state.get('x_lims'), state.get('y_lims'))
                        content = dcc.Graph(figure=fig, className="dash-graph", config={'displayModeBar': False})
                    elif job in ['1D_HISTO_VS_STATS', '1D_STATS_VS_HISTO']:
                        inv = state.get('inv1') if job == '1D_HISTO_VS_STATS' else state.get('inv2')
                        fig = create_1D_histo_figure(state.get('figure_data_histo',{}), state.get('title',''), inv, state.get('log_scale',True))
                        content = dcc.Graph(figure=fig, className="dash-graph", config={'displayModeBar': False})
                    elif job == '1D_STATS_VS_STATS':
                        content = build_full_stats_table(state, use_sci_notation=sci_pref)
                else:
                    content = build_full_stats_table(state, use_sci_notation=sci_pref)
                    
                overlay = ""
                if view == 'graph' and job == '3D_HEATMAP' and state.get('stats'):
                    s = state['stats']
                    pop = format_stat_value(s.get('population'), sci_pref) if s.get('population') is not None else 'N/A'
                    px = format_stat_value(s.get('peak_x'), sci_pref) if s.get('peak_x') is not None else 'N/A'
                    py = format_stat_value(s.get('peak_y'), sci_pref) if s.get('peak_y') is not None else 'N/A'
                    overlay = html.Div(className="stats-overlay", children=[
                        html.P(f"Pop: {pop}"),
                        html.P(f"Peak: ({px}, {py})")
                    ])
                    
                panel_div = html.Div(
                    className="graph-item",
                    children=[
                        content,
                        overlay if overlay else None,
                        buttons
                    ]
                )
                outputs.append(panel_div)
            except Exception as e:
                print(f"[V8 DEBUG] CRITICAL ERROR rendering panel {i}:\n{traceback.format_exc()}")
                outputs.append(
                    html.Div(
                        className="graph-item d-flex flex-column text-danger p-3 text-center justify-content-center",
                        children=[html.I(className="bi bi-exclamation-triangle fs-1"), html.Span(f"Render Error: {e}")]
                    )
                )
            
        print(f"[V8 DEBUG] Exiting render_all_panels, emitting {len(outputs)} DOM objects to matched columns.")
        return outputs

    @app.callback(
        Output('help-modal', 'is_open'),
        Input('help-btn-footer', 'n_clicks'),
        Input('help-btn-sidebar', 'n_clicks'),
        Input('help-btn-mobile', 'n_clicks'),
        State('help-modal', 'is_open'),
        prevent_initial_call=True
    )
    def toggle_help_modal(n_footer, n_sidebar, n_mobile, is_open):
        return not is_open