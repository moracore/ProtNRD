import json
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
from constants import (
    INVARIANT_SHORTHAND, N_RAINBOW, MAX_GRAPHS
)
import math
import time

# --- HELPER: 1D Figure Generators ---

def create_1D_histo_figure(data, title, inv_name):
    """Creates a Plotly Bar chart for 1D Histogram data."""
    fig = go.Figure(data=[go.Bar(
        x=data.get('bins', []),
        y=data.get('counts', []),
        marker_color='#0d6efd'
    )])
    fig.update_layout(
        title=title,
        xaxis_title=INVARIANT_SHORTHAND.get(inv_name, inv_name),
        yaxis_title="Frequency",
        margin=dict(l=20, r=20, b=30, t=40),
        uirevision=str(time.time()) # Force redraw
    )
    return fig

def create_stat_card(data, title, inv_name):
    """Creates a Dash Bootstrap Card for 1D Stats data."""
    if not data:
        return dbc.Card(dbc.CardBody("No stats data available."), className="stat-card h-100")
    
    q = data.get('quartiles', {})
    inv_label = INVARIANT_SHORTHAND.get(inv_name, inv_name)
    
    return dbc.Card([
        dbc.CardHeader(title),
        dbc.CardBody(
            dbc.ListGroup([
                dbc.ListGroupItem([
                    html.Span("Invariant", className="stat-label"),
                    html.Span(inv_label, className="stat-value")
                ], className="d-flex justify-content-between"),
                dbc.ListGroupItem([
                    html.Span("Population", className="stat-label"),
                    html.Span(f"{data.get('population', 0):,}", className="stat-value")
                ], className="d-flex justify-content-between"),
                dbc.ListGroupItem([
                    html.Span("Mean", className="stat-label"),
                    html.Span(f"{data.get('mean', 0):.2f}", className="stat-value")
                ], className="d-flex justify-content-between"),
                dbc.ListGroupItem([
                    html.Span("Variance", className="stat-label"),
                    html.Span(f"{data.get('variance', 0):.2f}", className="stat-value")
                ], className="d-flex justify-content-between"),
                dbc.ListGroupItem([
                    html.Span("Median (50%)", className="stat-label"),
                    html.Span(f"{q.get('median', 'N/A'):.2f}" if q.get('median') is not None else 'N/A', className="stat-value")
                ], className="d-flex justify-content-between"),
                dbc.ListGroupItem([
                    html.Span("Min", className="stat-label"),
                    html.Span(f"{q.get('min', 'N/A'):.2f}" if q.get('min') is not None else 'N/A', className="stat-value")
                ], className="d-flex justify-content-between"),
                dbc.ListGroupItem([
                    html.Span("Max", className="stat-label"),
                    html.Span(f"{q.get('max', 'N/A'):.2f}" if q.get('max') is not None else 'N/A', className="stat-value")
                ], className="d-flex justify-content-between"),
            ], flush=True, className="stat-list-group"),
            className="p-0" # Remove card body padding to let list group fill
        )
    ], className="stat-card h-100")


# --- HELPER: 3D Figure Generator (Refactored for Dynamic Tiling & Transparency) ---

def create_3D_figure(data, title, uirevision_key, log_scale, colormap, inv1_name=None, inv2_name=None, x_lims=None, y_lims=None):
    # --- HELPER FUNCTIONS (scoped inside) ---
    def get_invariant_type(inv_name):
        if not inv_name: return 'unknown'
        if inv_name in ['tau_NA', 'tau_AC', 'tau_CN', 'angle_N', 'angle_A', 'angle_C']: return 'angular'
        if 'length' in inv_name: return 'length'
        return 'unknown'

    def _get_axis_range(inv_name):
        inv_type = get_invariant_type(inv_name)
        if inv_type == 'angular': return [-180, 180]
        if inv_type == 'length': return [1, 2]
        return None

    # --- Accept both dense (x,y,z) and sparse ('points') formats ---
    # Preferred dense: data = {'x': [...], 'y': [...], 'z': [[...]]} where z shape == (len(y), len(x))
    # Sparse: data = {'points': [(x_center, y_center, freq), ...]}
    original_x_data = np.array(data.get('x', []))
    original_y_data = np.array(data.get('y', []))
    original_z_data = np.array(data.get('z', []))

    if 'points' in data and data.get('points') is not None:
        pts = data.get('points') or []
        if len(pts) == 0:
            original_x_data = np.array([])
            original_y_data = np.array([])
            original_z_data = np.array([[]])
        else:
            # Unpack sparse triples
            xs, ys, zs = zip(*pts)
            xs = np.array(xs, dtype=float)
            ys = np.array(ys, dtype=float)
            zs = np.array(zs, dtype=float)

            # Unique sorted bin centers
            x_centers = np.unique(xs)
            y_centers = np.unique(ys)

            # Build dense grid with rows -> y, cols -> x (shape: (len(y), len(x)))
            z_grid = np.zeros((len(y_centers), len(x_centers)), dtype=float)

            # Map each (x,y) to an index and fill
            x_idx_map = {v: i for i, v in enumerate(x_centers)}
            y_idx_map = {v: i for i, v in enumerate(y_centers)}

            for x_val, y_val, freq in zip(xs, ys, zs):
                xi = x_idx_map[x_val]
                yi = y_idx_map[y_val]
                # Accumulate in case duplicates exist
                z_grid[yi, xi] += float(freq)

            # Set originals in the renderer's canonical orientation
            original_x_data = x_centers.copy()
            original_y_data = y_centers.copy()
            original_z_data = z_grid.copy()  # shape (len(y), len(x))

    # --- Validate shapes and handle empty ---
    if original_z_data.size == 0 or original_x_data.size == 0 or original_y_data.size == 0 or original_z_data.ndim != 2:
         print("Warning: Invalid or empty data received for 3D plot.")
         fig = go.Figure()
         fig.update_layout(title=f"{title} (No Data)", margin=dict(l=0, r=0, b=0, t=40))
         return fig

    # From here on, keep your existing logic (tiling / axis ranges / NaN handling)
    z_axis_title = "Log(Frequency + 1)" if log_scale else "Frequency"
    scene_config = {'zaxis_title': z_axis_title, 'camera': dict(eye=dict(x=-1.5, y=-2.5, z=1.5))}
    cycle_range = 360

    # final_* variables are copies we can mutate for tiling/sorting
    final_x_data = original_x_data.copy()
    final_y_data = original_y_data.copy()
    final_z_data = original_z_data.copy()  # shape: (len(y), len(x))

    x_tile_range = [0]
    y_tile_range = [0]
    sort_x_indices = np.arange(len(final_x_data))
    sort_y_indices = np.arange(len(final_y_data))

    # Dynamic tiling / axis config
    for axis, inv_name, original_axis_data, limits in [
            ('xaxis', inv1_name, original_x_data, x_lims),
            ('yaxis', inv2_name, original_y_data, y_lims)]:

        scene_config[axis] = {'title': INVARIANT_SHORTHAND.get(inv_name, inv_name or axis[0].upper())}
        inv_type = get_invariant_type(inv_name)
        is_angular = (inv_type == 'angular')

        current_lims = _get_axis_range(inv_name)
        if limits and limits[0] is not None and limits[1] is not None and limits[0] < limits[1]:
            current_lims = limits

        min_lim, max_lim = current_lims if current_lims else (None, None)

        if min_lim is not None and max_lim is not None:
             scene_config[axis]['range'] = [min_lim, max_lim]
             if is_angular and original_axis_data.size > 0:
                 data_min = original_axis_data.min()
                 coord_min = math.floor((min_lim - data_min) / cycle_range)
                 coord_max = math.ceil((max_lim - data_min) / cycle_range)
                 tile_indices = range(coord_min - 1, coord_max + 1)
                 if axis == 'xaxis':
                     x_tile_range = [i * cycle_range for i in tile_indices]
                 else:
                     y_tile_range = [i * cycle_range for i in tile_indices]

                 tick_step = 45
                 start_tick = math.ceil(min_lim / tick_step) * tick_step
                 tickvals = [t for t in range(start_tick, int(max_lim) + tick_step, tick_step)]
                 # FIX APPLIED HERE: Use raw tickvals as ticktext to show continuous angle.
                 ticktext = [str(v) for v in tickvals]
                 scene_config[axis]['tickvals'] = tickvals
                 scene_config[axis]['ticktext'] = ticktext

    # Tiling: if more than one tile offset, expand arrays. Note: original_z_data is (len(y), len(x))
    if len(x_tile_range) > 1 or len(y_tile_range) > 1:
        # Tile final_x_data and final_y_data
        final_x_data = np.concatenate([original_x_data + offset for offset in x_tile_range])
        final_y_data = np.concatenate([original_y_data + offset for offset in y_tile_range])

        # Tile Z grid: repeat original_z_data across tiles:
        final_z_data = np.tile(original_z_data, (len(y_tile_range), len(x_tile_range)))  # shape: (len(y)*ytiles, len(x)*xtiles)

        # Sort tiled X and corresponding Z columns
        sort_x_indices = np.argsort(final_x_data)
        final_x_data = final_x_data[sort_x_indices]
        if final_z_data.ndim == 2 and final_z_data.shape[1] == len(sort_x_indices):
            final_z_data = final_z_data[:, sort_x_indices]

        # Sort tiled Y and corresponding Z rows
        sort_y_indices = np.argsort(final_y_data)
        final_y_data = final_y_data[sort_y_indices]
        if final_z_data.ndim == 2 and final_z_data.shape[0] == len(sort_y_indices):
            final_z_data = final_z_data[sort_y_indices, :]

    # Process Z for display
    if final_z_data.ndim != 2:
        print("Warning: Z data became invalid after tiling.")
        z_processed = np.array([[]])
        final_x_data, final_y_data = np.array([]), np.array([])
    else:
        z_processed = final_z_data.astype(float)
        # keep zeros -> convert to NaN for transparency (existing behavior)
        z_processed[z_processed == 0] = np.nan

    finite_z_original = original_z_data.astype(float)
    finite_z_original = finite_z_original[np.isfinite(finite_z_original) & (finite_z_original > 0)]

    z_display_values = np.log10(z_processed + 1) if log_scale else z_processed
    color_values = np.log10(z_processed + 1e-9)

    cmin_val, cmax_val = (0, 1)
    if finite_z_original.size > 0:
        cmin_val = np.log10(1)
        cmax_val = np.log10(np.max(finite_z_original) + 1)

    fig = go.Figure(data=[go.Surface(
        x=final_x_data, y=final_y_data, z=z_display_values,
        surfacecolor=color_values,
        colorscale=N_RAINBOW if colormap == "Custom Rainbow" else colormap,
        showscale=False,
        cmin=cmin_val,
        cmax=cmax_val,
        lighting=dict(ambient=0.8, diffuse=1, specular=0.2)
    )])
    fig.update_layout(
        title=title,
        uirevision=uirevision_key,
        scene=scene_config,
        margin=dict(l=0, r=0, b=0, t=40)
    )
    return fig

# --- MAIN RENDERING CALLBACK ---

def register_rendering_callbacks(app):
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
        """
        Renders the content for all graph panels based on their stored state.
        """
        panel_states = json.loads(panel_states_json or '{}')
        outputs = []
        status_update = no_update

        if ctx.triggered_id == 'panel-states-store' and current_status:
            status_update = "" # Clear status on data update

        panel_style = {'position': 'relative', 'height': '100%'}
        buttons_style = {
            'position': 'absolute', 'bottom': '5px', 'right': '5px',
            'zIndex': 10, 'display': 'flex', 'gap': '0.25rem'
        }

        for i in range(MAX_GRAPHS):
            state = panel_states.get(str(i))
            is_active = (i == active_panel_index)
            job_type = state.get('job_type') if state else None
            has_content = bool(state and (state.get('figure_data') or state.get('figure_data_histo') or state.get('figure_data_stats1')))

            buttons = html.Div([
                dbc.Button(html.I(className="bi bi-box-arrow-up-right"), id={'type': 'focus-button', 'index': i}, size="sm", title="Focus", disabled=not has_content),
                dbc.Button(html.I(className="bi bi-download"), id={'type': 'download-button', 'index': i}, size="sm", title="Download", disabled=not has_content),
                dbc.Button(html.I(className="bi bi-gear-fill"), id={'type': 'config-button', 'index': i}, size="sm", color="primary" if is_active else "secondary", title="Configure"),
                dbc.Button(html.I(className="bi bi-x-lg"), id={'type': 'clear-button', 'index': i}, size="sm", color="danger", title="Clear", disabled=not state),
            ], style=buttons_style)

            main_content = None
            try:
                if state and state.get('error'):
                    main_content = html.Div([html.I(className="bi bi-exclamation-triangle-fill text-warning"), html.P(state['error'], className="text-center small mt-2")], className="d-flex flex-column h-100 justify-content-center align-items-center placeholder-panel active")

                elif job_type == '3D_HEATMAP':
                    stats, peak_loc = state.get('stats', {}), state.get('stats', {}).get('peak_location', {})
                    peak_x, peak_y = peak_loc.get('x', 'N/A'), peak_loc.get('y', 'N/A')
                    stats_overlay = html.Div([
                        html.P(f"# {stats.get('total_points', 0):,}", title="Total Data Points"),
                        html.P(f"Peak: ({peak_x:.1f}, {peak_y:.1f})" if isinstance(peak_x, (int, float)) else "Peak: N/A", title="Peak Location"),
                        html.P(f"▲ {stats.get('peak_frequency', 0):,}", title="Peak Frequency")
                    ], className="stats-overlay")
                    x_lims, y_lims = state.get('x_lims'), state.get('y_lims')
                    fig = create_3D_figure(state.get('figure_data',{}), state['title'], state['uirevision_key'], scale_bool, colormap, state.get('inv1'), state.get('inv2'), x_lims, y_lims)
                    main_content = html.Div([dcc.Graph(figure=fig, style={'height': '100%'}), stats_overlay], className="graph-item h-100")

                elif job_type == '1D_HISTO_VS_STATS':
                    fig = create_1D_histo_figure(state['figure_data_histo'], f"1D Histo: {state['inv1']}", state['inv1'])
                    card = create_stat_card(state['stats_stats'], f"1D Stats: {state['inv2']}", state['inv2'])
                    main_content = html.Div([
                        dcc.Graph(figure=fig, style={'height': '60%'}),
                        html.Div(card, style={'height': '40%', 'overflow-y': 'auto', 'padding': '0.5rem'})
                    ], className="graph-item h-100 d-flex flex-column")

                elif job_type == '1D_STATS_VS_HISTO':
                    fig = create_1D_histo_figure(state['figure_data_histo'], f"1D Histo: {state['inv2']}", state['inv2'])
                    card = create_stat_card(state['stats_stats'], f"1D Stats: {state['inv1']}", state['inv1'])
                    main_content = html.Div([
                        dcc.Graph(figure=fig, style={'height': '60%'}),
                        html.Div(card, style={'height': '40%', 'overflow-y': 'auto', 'padding': '0.5rem'})
                    ], className="graph-item h-100 d-flex flex-column")

                elif job_type == '1D_STATS_VS_STATS':
                    card1 = create_stat_card(state['figure_data_stats1'], f"Stats: {state['inv1']}", state['inv1'])
                    card2 = create_stat_card(state['figure_data_stats2'], f"Stats: {state['inv2']}", state['inv2'])
                    main_content = html.Div(dbc.Row([
                        dbc.Col(card1, width=6, className="h-100"),
                        dbc.Col(card2, width=6, className="h-100")
                    ], className="g-2 h-100"), className="graph-item h-100 p-2")

                else:
                    main_content = html.Div(html.I(className="bi bi-plus-lg"), id={'type': 'placeholder-button', 'index': i}, className=f"placeholder-panel d-flex h-100 justify-content-center align-items-center {'placeholder-active' if is_active else ''}")

            except Exception as e:
                print(f"ERROR during panel rendering (index {i}): {e}")
                import traceback
                traceback.print_exc()
                main_content = html.Div([
                    html.I(className="bi bi-exclamation-octagon-fill text-danger"),
                    html.P(f"Rendering Error: {e}", className="text-center small mt-2")
                ], className="d-flex flex-column h-100 justify-content-center align-items-center placeholder-panel")

            outputs.append(html.Div([buttons, main_content], style=panel_style))

        return outputs + [status_update]

