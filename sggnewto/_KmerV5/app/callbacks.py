import json
import sqlite3
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
from constants import DB_PATH, INVARIANT_SHORTHAND, N_RAINBOW, MAX_GRAPHS, INVARIANT_ORDER
import math

def register_callbacks(app: Dash):
    """Registers all callbacks for the v5 app."""

    # --- HELPER FUNCTIONS ---
    def get_invariant_type(inv_name):
        if not inv_name: return 'unknown'
        if inv_name == 'tau_NA': return 'phi'
        if inv_name == 'tau_AC': return 'psi'
        if inv_name == 'tau_CN': return 'omega'
        if 'length' in inv_name: return 'length'
        if 'angle' in inv_name: return 'angle'
        if 'tau' in inv_name: return 'tau'
        return 'unknown'

    def _get_axis_range(inv_name):
        inv_type = get_invariant_type(inv_name)
        if inv_type == 'phi': return [0, 360]
        if inv_type in ['psi', 'omega']: return [-90, 270]
        if inv_type in ['angle', 'tau']: return [0, 360] 
        if inv_type == 'length': return [1, 2]
        return None

    def create_figure(data, title, uirevision_key, log_scale, colormap, inv1_name=None, inv2_name=None, x_lims=None, y_lims=None):
        z_data = np.array(data.get('z', []))
        plot_x_data = np.array(data.get('x', []))
        plot_y_data = np.array(data.get('y', []))

        z_axis_title = "Log(Frequency + 1)" if log_scale else "Frequency"
        scene_config = {'zaxis_title': z_axis_title, 'camera': dict(eye=dict(x=-1.5, y=-2.5, z=1.5))}
        
        # --- FIX: Implement data tiling for cyclical plots ---
        for axis, inv_name, limits in [('xaxis', inv1_name, x_lims), ('yaxis', inv2_name, y_lims)]:
            scene_config[axis] = {'title': INVARIANT_SHORTHAND.get(inv_name, inv_name or axis[0].upper())}
            inv_type = get_invariant_type(inv_name)
            is_angular = 'angle' in inv_type or inv_type in ['phi', 'psi', 'omega', 'tau']

            if limits and limits[0] is not None and limits[1] is not None and is_angular:
                scene_config[axis]['range'] = limits
                min_lim, max_lim = limits
                
                # Determine how many times to tile the data
                data_range = plot_x_data.max() - plot_x_data.min() if axis == 'xaxis' else plot_y_data.max() - plot_y_data.min()
                num_tiles = math.ceil((max_lim - min_lim) / data_range)
                
                if axis == 'xaxis' and num_tiles > 1:
                    original_x = plot_x_data.copy()
                    original_z = z_data.copy()
                    plot_x_data = np.array([])
                    z_data = np.array([]).reshape(len(original_z), 0)
                    
                    start_offset = math.floor(min_lim / data_range) * data_range
                    
                    for i in range(num_tiles + 2): # Add buffer tiles
                        offset = start_offset + i * data_range
                        new_x = original_x + offset
                        plot_x_data = np.concatenate([plot_x_data, new_x])
                        z_data = np.concatenate([z_data, original_z], axis=1)

                elif axis == 'yaxis' and num_tiles > 1:
                    original_y = plot_y_data.copy()
                    original_z = z_data.copy()
                    plot_y_data = np.array([])
                    z_data = np.array([]).reshape(0, len(original_z[0]))
                    
                    start_offset = math.floor(min_lim / data_range) * data_range
                    
                    for i in range(num_tiles + 2):
                        offset = start_offset + i * data_range
                        new_y = original_y + offset
                        plot_y_data = np.concatenate([plot_y_data, new_y])
                        z_data = np.concatenate([z_data, original_z], axis=0)
                
                # Sort the tiled data to prevent plotting artifacts
                if axis == 'xaxis':
                    sort_indices = np.argsort(plot_x_data)
                    plot_x_data = plot_x_data[sort_indices]
                    z_data = z_data[:, sort_indices]
                elif axis == 'yaxis':
                    sort_indices = np.argsort(plot_y_data)
                    plot_y_data = plot_y_data[sort_indices]
                    z_data = z_data[sort_indices, :]

                start_tick = math.ceil(min_lim / 45) * 45
                tickvals = [t for t in range(start_tick, int(max_lim) + 1, 45)]
                ticktext = [v % 360 for v in tickvals]
                scene_config[axis]['tickvals'] = tickvals
                scene_config[axis]['ticktext'] = ticktext

            elif (default_range := _get_axis_range(inv_name)):
                scene_config[axis]['range'] = default_range
                if inv_type in ['phi', 'angle', 'tau']:
                    scene_config[axis]['tickvals'] = list(range(0, 361, 45))
                elif inv_type in ['psi', 'omega']:
                    scene_config[axis]['tickvals'] = list(range(-90, 271, 45))

        z_processed = z_data.copy().astype(float)
        z_processed[z_processed == 0] = np.nan
        finite_z = z_processed[np.isfinite(z_processed)]
        z_display_values = np.log10(z_processed + 1) if log_scale else z_processed
        color_values = np.log10(z_processed + 1)
        cmin_val, cmax_val = (0, 1)
        if finite_z.size > 0:
            cmin_val, cmax_val = np.log10(1), np.log10(np.max(finite_z) + 1)

        fig = go.Figure(data=[go.Surface(x=plot_x_data, y=plot_y_data, z=z_display_values, surfacecolor=color_values, colorscale=N_RAINBOW if colormap == "Custom Rainbow" else colormap, showscale=False, cmin=cmin_val, cmax=cmax_val)])
        fig.update_layout(title=title, uirevision=uirevision_key, scene=scene_config, margin=dict(l=0, r=0, b=0, t=40))
        return fig

    # --- MAIN RENDERING & STATUS CLEAR ---
    @app.callback(
        [Output({'type': 'graph-col', 'index': i}, 'children') for i in range(MAX_GRAPHS)] + 
        [Output('status-message-store', 'data', allow_duplicate=True)],
        Input('panel-states-store', 'data'),
        Input('active-panel-store', 'data'),
        Input('scale-switch', 'value'),
        Input('colormap-dropdown', 'value'),
        State('status-message-store', 'data'),
        prevent_initial_call=True
    )
    def update_all_panels(panel_states_json, active_panel_index, scale_bool, colormap, current_status):
        panel_states = json.loads(panel_states_json or '{}')
        outputs = []

        panel_style = {'position': 'relative', 'height': '100%'}
        buttons_style = {
            'position': 'absolute', 'bottom': '5px', 'right': '5px',
            'zIndex': 10, 'display': 'flex', 'gap': '0.25rem'
        }

        for i in range(MAX_GRAPHS):
            state = panel_states.get(str(i))
            is_active, has_graph = (i == active_panel_index), (state and state.get('figure_data'))
            
            buttons = html.Div([
                dbc.Button(html.I(className="bi bi-box-arrow-up-right"), id={'type': 'focus-button', 'index': i}, size="sm", title="Focus", disabled=not has_graph),
                dbc.Button(html.I(className="bi bi-download"), id={'type': 'download-button', 'index': i}, size="sm", title="Download", disabled=not has_graph),
                dbc.Button(html.I(className="bi bi-gear-fill"), id={'type': 'config-button', 'index': i}, size="sm", color="primary" if is_active else "secondary", title="Configure"),
                dbc.Button(html.I(className="bi bi-x-lg"), id={'type': 'clear-button', 'index': i}, size="sm", color="danger", title="Clear", disabled=not state),
            ], style=buttons_style)
            
            main_content = None
            if has_graph:
                stats, peak_loc = state.get('stats', {}), state.get('stats', {}).get('peak_location', {})
                peak_x, peak_y = peak_loc.get('x', 'N/A'), peak_loc.get('y', 'N/A')
                stats_overlay = html.Div([
                    html.P(f"# {stats.get('total_points', 0):,}", title="Total Data Points"),
                    html.P(f"Peak: ({peak_x:.1f}, {peak_y:.1f})" if isinstance(peak_x, (int, float)) else "Peak: N/A", title="Peak Location"),
                    html.P(f"▲ {stats.get('peak_frequency', 0):,}", title="Peak Frequency")
                ], className="stats-overlay")
                x_lims = state.get('x_lims')
                y_lims = state.get('y_lims')
                fig = create_figure(state['figure_data'], state['title'], state['uirevision_key'], scale_bool, colormap, state.get('inv1'), state.get('inv2'), x_lims, y_lims)
                main_content = html.Div([dcc.Graph(figure=fig, style={'height': '100%'}), stats_overlay], className="graph-item h-100")
            elif state and state.get('error'):
                main_content = html.Div([html.I(className="bi bi-exclamation-triangle-fill text-warning"), html.P(state['error'], className="text-center small mt-2")], className="d-flex flex-column h-100 justify-content-center align-items-center placeholder-panel active")
            else:
                main_content = html.Div(html.I(className="bi bi-plus-lg"), id={'type': 'placeholder-button', 'index': i}, className=f"placeholder-panel d-flex h-100 justify-content-center align-items-center {'placeholder-active' if is_active else ''}")
            
            panel_with_buttons = html.Div([main_content, buttons], style=panel_style)
            outputs.append(dcc.Loading(children=panel_with_buttons, type="circle", fullscreen=False, parent_className="h-100"))

        status_update = no_update
        if current_status == "Generating graph...":
            status_update = "" 
        return outputs + [status_update]

    # --- STATUS INDICATOR CALLBACKS ---
    @app.callback(
        Output('status-indicator', 'children'),
        Output('status-indicator', 'style'),
        Input('status-message-store', 'data'),
        State('status-indicator', 'style')
    )
    def update_status_indicator(message, current_style):
        current_style['opacity'] = 1 if message else 0
        return message, current_style

    @app.callback(
        Output('status-message-store', 'data', allow_duplicate=True),
        Output('status-clear-interval', 'disabled'),
        Input('status-clear-interval', 'n_intervals'),
        prevent_initial_call=True
    )
    def clear_status_message_on_interval(n_intervals):
        if n_intervals >= 1: return "", True 
        return no_update, no_update

    # --- DATA GENERATION & STATE MANAGEMENT ---
    @app.callback(
        Output('graph-job-store', 'data'),
        Output('status-message-store', 'data'),
        Input('generate-graph-button', 'n_clicks'),
        State('active-panel-store', 'data'),
        State('inv1-dropdown', 'value'),
        State('inv2-dropdown', 'value'),
        State('offset-dropdown', 'value'),
        State('xaxis-min-input', 'value'),
        State('xaxis-max-input', 'value'),
        State('yaxis-min-input', 'value'),
        State('yaxis-max-input', 'value'),
        prevent_initial_call=True
    )
    def trigger_graph_generation(n_clicks, active_panel, inv1, inv2, offset, x_min, x_max, y_min, y_max):
        if not n_clicks: return no_update, no_update
        job_spec = {
            'panel_id': str(active_panel), 'inv1': inv1, 'inv2': inv2, 'offset': offset, 
            'n_clicks': n_clicks, 'x_lims': [x_min, x_max], 'y_lims': [y_min, y_max]
        }
        return job_spec, "Generating graph..."

    @app.callback(
        Output('panel-states-store', 'data'),
        Input('graph-job-store', 'data'),
        State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def generate_graph(job_spec, panel_states_json):
        if not job_spec: return no_update
        panel_states = json.loads(panel_states_json or '{}')
        panel_id, inv1, inv2, offset = job_spec['panel_id'], job_spec['inv1'], job_spec['inv2'], job_spec['offset']
        
        try:
            swapped = False
            if offset == 0 and inv1 != inv2:
                type_order = {'length': 0, 'angle': 1, 'phi': 2, 'psi': 2, 'omega': 2, 'tau': 2}
                key_inv1, key_inv2 = sorted([inv1, inv2], key=lambda i: (type_order.get(get_invariant_type(i), 3), INVARIANT_ORDER.index(i)))
                if inv1 != key_inv1:
                    swapped = True
                plot_key = f"{key_inv1}_vs_{key_inv2}_Any_Any_bin%"
            elif offset != 0:
                plot_key = f"{inv1}_vs_{inv2}+{offset}_Any_Any_bin%"
            else: 
                plot_key = f"{inv1}_vs_{inv2}_Any_Any_bin%"

            with sqlite3.connect(DB_PATH) as conn:
                plot_result = conn.execute("SELECT heatmap_data FROM v5_pairwise_cache WHERE plot_key LIKE ?", (plot_key,)).fetchone()
                stats_result = conn.execute("SELECT stats_data FROM v5_pairwise_stats WHERE plot_key LIKE ?", (plot_key,)).fetchone()

            if not plot_result or not stats_result:
                panel_states[panel_id] = {'error': f"No data found for: {plot_key.replace('%', '')}"}
            else:
                figure_data = json.loads(plot_result[0])
                stats_data = json.loads(stats_result[0])

                if swapped:
                    figure_data['x'], figure_data['y'] = figure_data['y'], figure_data['x']
                    figure_data['z'] = np.array(figure_data['z']).T.tolist()
                    if 'peak_location' in stats_data:
                        stats_data['peak_location']['x'], stats_data['peak_location']['y'] = stats_data['peak_location']['y'], stats_data['peak_location']['x']

                title = f"{INVARIANT_SHORTHAND.get(inv1, inv1)} vs {INVARIANT_SHORTHAND.get(inv2, inv2)}" + (f" + {offset}" if offset != 0 else "")
                panel_states[panel_id] = {
                    'inv1': inv1, 'inv2': inv2, 'offset': offset, 'title': title, 
                    'figure_data': figure_data, 'stats': stats_data, 
                    'uirevision_key': f"{inv1}_{inv2}_{offset}_{job_spec['n_clicks']}",
                    'x_lims': job_spec['x_lims'], 'y_lims': job_spec['y_lims']
                }
        except Exception as e:
            panel_states[panel_id] = {'error': f"Data error: {e}"}
        return json.dumps(panel_states)

    @app.callback(
        Output('active-panel-store', 'data'),
        Input({'type': 'placeholder-button', 'index': ALL}, 'n_clicks'),
        Input({'type': 'config-button', 'index': ALL}, 'n_clicks'),
        State('active-panel-store', 'data'),
        prevent_initial_call=True
    )
    def set_active_panel(p_clicks, c_clicks, active_idx):
        if not ctx.triggered_id: return no_update
        return ctx.triggered_id['index'] if ctx.triggered_id['index'] != active_idx else no_update
    
    # --- FIX: Added callback to update limit labels dynamically ---
    @app.callback(
        Output('xaxis-limit-label', 'children'),
        Output('yaxis-limit-label', 'children'),
        Input('inv1-dropdown', 'value'),
        Input('inv2-dropdown', 'value')
    )
    def update_limit_labels(inv1, inv2):
        label1 = f"{INVARIANT_SHORTHAND.get(inv1, 'X')}-axis limits"
        label2 = f"{INVARIANT_SHORTHAND.get(inv2, 'Y')}-axis limits"
        return label1, label2

    @app.callback(
        Output('inv1-dropdown', 'value'), Output('inv2-dropdown', 'value'),
        Output('offset-dropdown', 'value'), Output('active-panel-display', 'children'),
        Output('xaxis-min-input', 'value'), Output('xaxis-max-input', 'value'),
        Output('yaxis-min-input', 'value'), Output('yaxis-max-input', 'value'),
        Input('active-panel-store', 'data'),
        State('panel-states-store', 'data')
    )
    def load_config_to_side_panel(active_idx, states_json):
        states = json.loads(states_json or '{}').get(str(active_idx))
        title = f"Configure Panel {active_idx + 1}"
        if not states or 'error' in states:
            return 'tau_NA', 'tau_AC', 0, title, None, None, None, None
        
        x_lims = states.get('x_lims', [None, None])
        y_lims = states.get('y_lims', [None, None])
        
        return (states.get('inv1', 'tau_NA'), states.get('inv2', 'tau_AC'), 
                states.get('offset', 0), title,
                x_lims[0], x_lims[1], y_lims[0], y_lims[1])

    # --- MODALS, CLEAR, AND DOWNLOAD ---
    @app.callback(
        Output("focus-modal", "is_open"), Output("focus-graph", "figure"), Output("focus-modal-header", "children"),
        Input({'type': 'focus-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'), State('scale-switch', 'value'), State('colormap-dropdown', 'value'),
        prevent_initial_call=True
    )
    def handle_focus_modal(n_clicks, states_json, scale, colormap):
        if not any(n_clicks): return no_update
        state = json.loads(states_json or '{}').get(str(ctx.triggered_id['index']))
        if not state or 'figure_data' not in state: return no_update
        
        x_lims = state.get('x_lims')
        y_lims = state.get('y_lims')
        fig = create_figure(state['figure_data'], state['title'], state['uirevision_key'], scale, colormap, state.get('inv1'), state.get('inv2'), x_lims, y_lims)
        return True, fig, state.get('title', 'Focused Graph')

    @app.callback(
        Output('confirm-clear-modal', 'is_open'), Output('last-clicked-panel-store', 'data'),
        Input({'type': 'clear-button', 'index': ALL}, 'n_clicks'),
        Input('cancel-clear-button', 'n_clicks'),
        State('confirm-clear-modal', 'is_open'),
        prevent_initial_call=True
    )
    def toggle_clear_confirmation(clear_clicks, cancel_click, is_open):
        if not ctx.triggered_id or ctx.triggered_id == 'cancel-clear-button': return False, no_update
        if isinstance(trigger_id := ctx.triggered_id, dict) and trigger_id.get('type') == 'clear-button' and ctx.triggered[0]['value']:
            return True, trigger_id.get('index')
        return is_open, no_update

    @app.callback(
        Output('panel-states-store', 'data', allow_duplicate=True),
        Output('confirm-clear-modal', 'is_open', allow_duplicate=True),
        Input('confirm-clear-button', 'n_clicks'),
        State('last-clicked-panel-store', 'data'), State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def execute_clear_panel(n_clicks, panel_idx, states_json):
        if n_clicks and panel_idx is not None:
            states = json.loads(states_json or '{}')
            states.pop(str(panel_idx), None)
            return json.dumps(states), False
        return no_update, True

    @app.callback(
        Output('download-html', 'data'),
        Output('status-message-store', 'data', allow_duplicate=True),
        Output('status-clear-interval', 'disabled', allow_duplicate=True),
        Input({'type': 'download-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'), State('scale-switch', 'value'), State('colormap-dropdown', 'value'),
        prevent_initial_call=True
    )
    def download_graph_as_html(n_clicks, states_json, scale, colormap):
        if not ctx.triggered_id or not any(n_clicks): return no_update, no_update, no_update
        state = json.loads(states_json or '{}').get(str(ctx.triggered_id['index']))
        if not state or 'figure_data' not in state: return no_update, "Download failed", False
        
        x_lims = state.get('x_lims')
        y_lims = state.get('y_lims')
        fig = create_figure(state['figure_data'], state['title'], state['uirevision_key'], scale, colormap, state.get('inv1'), state.get('inv2'), x_lims, y_lims)
        filename = f"{state['title'].replace(' ', '_')}.html"
        return dcc.send_string(fig.to_html(), filename), "Downloading HTML...", False

