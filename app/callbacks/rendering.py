import json
import numpy as np
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
from constants import (
    INVARIANT_SHORTHAND, N_RAINBOW, MAX_GRAPHS, TORSION_INVARIANTS
)
import math
import time

def format_stat_value(value, use_sci_notation=False, precision=3):
    """
    Formats a numeric value either as fixed-point or scientific notation.
    """
    if value is None:
        return "N/A"
    try:
        if use_sci_notation:
            return f"{value:.{precision}e}"
        else:
            if abs(value) < 1e-3 and abs(value) > 0:
                return f"{value:.{precision}e}"
            return f"{value:.{precision}f}"
    except (TypeError, ValueError):
        return str(value)

def normalize_angular_stat(value, limits, is_angular):
    """
    Shifts an angular statistic by 360 degrees if it falls outside
    the user-defined limits and a shifted value falls inside.
    """
    if not is_angular or value is None:
        return value
    
    try:
        min_lim, max_lim = limits
        if min_lim is None or max_lim is None:
            return value
    except (TypeError, ValueError):
        return value
        
    if min_lim < max_lim:
        if min_lim <= value <= max_lim:
            return value
        
        val_plus_360 = value + 360
        if min_lim <= val_plus_360 <= max_lim:
            return val_plus_360
            
        val_minus_360 = value - 360
        if min_lim <= val_minus_360 <= max_lim:
            return val_minus_360
            
    return value

def create_1D_histo_figure(data, title, inv_name, log_scale):
    """Creates a Plotly Bar chart for 1D Histogram data."""
    if not data:
        fig = go.Figure()
        fig.update_layout(
            title=f"{title} (No Histogram Data)", 
            xaxis_title=INVARIANT_SHORTHAND.get(inv_name, inv_name),
            margin=dict(l=20, r=20, b=30, t=40)
        )
        return fig
        
    fig = go.Figure(data=[go.Bar(
        x=data.get('bins', []),
        y=data.get('counts', []),
        marker_color='#003E7C'
    )])
    fig.update_layout(
        title=title,
        xaxis_title=INVARIANT_SHORTHAND.get(inv_name, inv_name),
        yaxis_title="Frequency",
        yaxis_type="log" if log_scale else "linear",
        margin=dict(l=20, r=20, b=30, t=40),
        uirevision=str(time.time())
    )
    return fig

def create_3D_figure(data, title, uirevision_key, log_scale, colormap, inv1_name=None, inv2_name=None, x_lims=None, y_lims=None):
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

    # Handle potentially empty data structure
    if not data:
         fig = go.Figure()
         fig.update_layout(title=f"{title} (No 3D Data)", margin=dict(l=0, r=0, b=0, t=40))
         return fig

    # "Original" refers to DB/DataFetching orientation (before flip)
    original_x_data = np.array(data.get('x', [])) # Data for Inv1
    original_y_data = np.array(data.get('y', [])) # Data for Inv2
    original_z_data = np.array(data.get('z', [])) # Z[inv2, inv1]

    if 'points' in data and data.get('points') is not None:
        pts = data.get('points') or []
        if len(pts) == 0:
            original_x_data, original_y_data, original_z_data = np.array([]), np.array([]), np.array([[]])
        else:
            xs, ys, zs = zip(*pts)
            xs, ys, zs = np.array(xs, dtype=float), np.array(ys, dtype=float), np.array(zs, dtype=float)
            x_centers, y_centers = np.unique(xs), np.unique(ys)
            z_grid = np.zeros((len(y_centers), len(x_centers)), dtype=float)
            x_idx_map, y_idx_map = {v: i for i, v in enumerate(x_centers)}, {v: i for i, v in enumerate(y_centers)}
            for x_val, y_val, freq in zip(xs, ys, zs):
                z_grid[y_idx_map[y_val], x_idx_map[x_val]] += float(freq)
            original_x_data, original_y_data, original_z_data = x_centers.copy(), y_centers.copy(), z_grid.copy()

    if original_z_data.size == 0 or original_x_data.size == 0 or original_y_data.size == 0 or original_z_data.ndim != 2:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (No Data)", margin=dict(l=0, r=0, b=0, t=40))
        return fig

    z_axis_title = "Log(Frequency + 1)" if log_scale else "Frequency"
    scene_config = {'zaxis_title': z_axis_title, 'camera': dict(eye=dict(x=-1.5, y=-2.5, z=1.5))}
    cycle_range = 360
    
    # Init tiles
    x_tile_range, y_tile_range = [0], [0]

    # --- AXIS CONFIGURATION ---
    # MODIFIED: Map Inv1 to Y-axis, Inv2 to X-axis
    # Note: original_x_data corresponds to Inv1, original_y_data corresponds to Inv2
    for axis, inv_name, original_axis_data, limits in [('yaxis', inv1_name, original_x_data, x_lims), ('xaxis', inv2_name, original_y_data, y_lims)]:
        scene_config[axis] = {'title': INVARIANT_SHORTHAND.get(inv_name, inv_name or axis[0].upper())}
        inv_type = get_invariant_type(inv_name)
        is_angular = (inv_type == 'angular')
        
        current_lims = _get_axis_range(inv_name)
        if limits and limits[0] is not None and limits[1] is not None and limits[0] < limits[1]:
            current_lims = limits
        min_lim, max_lim = current_lims if current_lims else (None, None)
        
        if min_lim is not None and max_lim is not None:
            scene_config[axis]['range'] = [min_lim, max_lim]
            
            # Tiling Logic
            if is_angular and original_axis_data.size > 0:
                data_min = original_axis_data.min()
                coord_min, coord_max = math.floor((min_lim - data_min) / cycle_range), math.ceil((max_lim - data_min) / cycle_range)
                tile_indices = range(coord_min - 1, coord_max + 1)
                
                if axis == 'xaxis':
                    x_tile_range = [i * cycle_range for i in tile_indices]
                else:
                    y_tile_range = [i * cycle_range for i in tile_indices]
                
                tick_step = 45
                start_tick = math.ceil(min_lim / tick_step) * tick_step
                tickvals = [t for t in range(start_tick, int(max_lim) + tick_step, tick_step)]
                ticktext = [str(v) for v in tickvals]
                scene_config[axis]['tickvals'] = tickvals
                scene_config[axis]['ticktext'] = ticktext

    # --- DATA GENERATION & TILING ---
    # Construct final arrays based on the axis mapping above.
    
    if len(x_tile_range) > 1 or len(y_tile_range) > 1:
        # Screen X comes from Inv2 (original_y) + x_tile_range
        final_x_data = np.concatenate([original_y_data + offset for offset in x_tile_range])
        
        # Screen Y comes from Inv1 (original_x) + y_tile_range
        final_y_data = np.concatenate([original_x_data + offset for offset in y_tile_range])
        
        # Z Matrix Transposition: 
        # Original Z is (Inv2_rows, Inv1_cols). 
        # Screen Z must be (Inv1_rows, Inv2_cols) to match (Screen Y, Screen X).
        z_transposed = original_z_data.T
        final_z_data = np.tile(z_transposed, (len(y_tile_range), len(x_tile_range)))
        
        # Sort X (Inv2)
        sort_x_indices = np.argsort(final_x_data)
        final_x_data = final_x_data[sort_x_indices]
        final_z_data = final_z_data[:, sort_x_indices]
        
        # Sort Y (Inv1)
        sort_y_indices = np.argsort(final_y_data)
        final_y_data = final_y_data[sort_y_indices]
        final_z_data = final_z_data[sort_y_indices, :]
    else:
        # No tiling, just simple swap
        final_x_data = original_y_data # Inv2 on X
        final_y_data = original_x_data # Inv1 on Y
        final_z_data = original_z_data.T # Transpose Z

    # --------------------------------

    if final_z_data.ndim != 2:
        z_processed = np.array([[]])
        final_x_data, final_y_data = np.array([]), np.array([])
    else:
        z_processed = final_z_data.astype(float)
        z_processed[z_processed == 0] = np.nan

    finite_z_original = original_z_data.astype(float)
    finite_z_original = finite_z_original[np.isfinite(finite_z_original) & (finite_z_original > 0)]
    z_display_values = np.log10(z_processed + 1) if log_scale else z_processed
    color_values = np.log10(z_processed + 1e-9)
    cmin_val, cmax_val = (0, 1)
    if finite_z_original.size > 0:
        cmin_val = np.log10(1)
        cmax_val = np.log10(np.max(finite_z_original) + 1)

    fig = go.Figure(data=[go.Surface(x=final_x_data, y=final_y_data, z=z_display_values, surfacecolor=color_values,
        colorscale=N_RAINBOW if colormap == "Custom Rainbow" else colormap, showscale=False, cmin=cmin_val, cmax=cmax_val,
        lighting=dict(ambient=0.8, diffuse=1, specular=0.2))])
    fig.update_layout(title=title, uirevision=uirevision_key, scene=scene_config, margin=dict(l=0, r=0, b=0, t=40))
    return fig

def build_3d_stats_overlay(stats_data):
    if not stats_data: return None
    pop = stats_data.get('population', 0); peak_x = stats_data.get('peak_x'); peak_y = stats_data.get('peak_y');
    
    peak_str = "Peak: N/A"
    if isinstance(peak_x, (int, float)) and isinstance(peak_y, (int, float)):
        peak_str = f"Peak: ({peak_x:.1f}, {peak_y:.1f})"

    return html.Div([
        html.P(f"# {pop:,}" if pop else "# N/A", title="Total Data Points"),
        html.P(peak_str, title="Peak Location"),
        html.P(f"▲ {stats_data.get('peak_freq', 0):,}", title="Peak Frequency")
    ], className="stats-overlay")

def create_combined_stats_table(panel_state, use_sci_notation=False):
    """
    Creates the compact stats table for the main graph view.
    Includes major 1D stats and pairwise stats.
    """
    stats = panel_state.get('full_v8_stats', {})
    if not stats:
        return dbc.Card(dbc.CardBody("No stats data available."), className="stat-card h-100")

    inv1 = panel_state.get('inv1'); inv2 = panel_state.get('inv2');
    inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1); inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2);
    title = panel_state.get('title', 'Statistics');
    
    x_lims = panel_state.get('x_lims'); y_lims = panel_state.get('y_lims');
    is_angular_x = inv1 in TORSION_INVARIANTS
    is_angular_y = inv2 in TORSION_INVARIANTS

    def get_stat(key, axis, p=3):
        val = stats.get(f'{key}_{axis}')
        if key in ['mean', 'min', 'median', 'max', 'peak']:
            limits = x_lims if axis == 'x' else y_lims
            is_angular = is_angular_x if axis == 'x' else is_angular_y
            val = normalize_angular_stat(val, limits, is_angular)
        return format_stat_value(val, use_sci_notation, precision=p)

    fmt_i = lambda k: f"{stats.get(k, 0):,}" if stats.get(k) is not None else "N/A"
    table_style = dict(bordered=True, striped=True, hover=True, size="sm")

    table_header = html.Thead(html.Tr([
        html.Th("Statistic"), html.Th(inv1_label), html.Th(inv2_label)
    ]))
    
    # Rows for the Combined Table
    table_body = html.Tbody([
        html.Tr([html.Td("Mean"), html.Td(get_stat('mean', 'x')), html.Td(get_stat('mean', 'y'))]),
        html.Tr([html.Td("Variance"), html.Td(get_stat('variance', 'x')), html.Td(get_stat('variance', 'y'))]),
        # Removed Median, Added Peak Loc & Freq
        html.Tr([html.Td("Min"), html.Td(get_stat('min', 'x')), html.Td(get_stat('min', 'y'))]),
        html.Tr([html.Td("Max"), html.Td(get_stat('max', 'x')), html.Td(get_stat('max', 'y'))]),
        html.Tr([html.Td("Peak Loc"), html.Td(get_stat('peak', 'x')), html.Td(get_stat('peak', 'y'))]),
        html.Tr([html.Td("Freq. at Peak"), html.Td(fmt_i('peak_freq_x')), html.Td(fmt_i('peak_freq_y'))]),
    ])
    comparison_table = dbc.Table([table_header, table_body], **table_style, className="mb-3")
    
    peak_x_str = get_stat('peak', 'x', p=2)
    peak_y_str = get_stat('peak', 'y', p=2)
    
    pairwise_rows = [
        html.Tr([html.Td("# of Data Points"), html.Td(fmt_i('population'))]),
    ]
    
    # Conditional Pairwise Stats (Covariance, Pearson)
    if stats.get('pearson_correlation') is not None:
        pairwise_rows.append(
            html.Tr([html.Td("Covariance"), html.Td(format_stat_value(stats.get('covariance'), use_sci_notation, precision=3))])
        )
        pairwise_rows.append(
            html.Tr([html.Td("Pearson's (ρ)"), html.Td(format_stat_value(stats.get('pearson_correlation'), use_sci_notation, precision=4))])
        )
        pairwise_rows.extend([
            html.Tr([html.Td("Peak Location"), html.Td(f"({peak_x_str}, {peak_y_str})")]),
            html.Tr([html.Td("Peak Frequency"), html.Td(fmt_i('peak_freq'))]),
        ])
    else:
        pairwise_rows.append(html.Tr([html.Td("Pairwise Stats"), html.Td("Not available for this combination")]))
    
    pairwise_table = dbc.Table(html.Tbody(pairwise_rows), **table_style)

    return dbc.Card([
        dbc.CardHeader(title),
        dbc.CardBody([
            html.H5("Comparison", className="card-subtitle mb-2 text-muted"),
            comparison_table,
            html.H5("Pairwise", className="card-subtitle mb-2 mt-3 text-muted"),
            pairwise_table
        ], className="p-3")
    ], className="stat-card h-100", style={'overflowY': 'auto'})

def build_full_stats_table(panel_state, use_sci_notation=False):
    """
    Creates the Full Stats table for the 'Stats View'.
    Includes everything found in DB (R, Bin, Win, etc).
    """
    stats = panel_state.get('full_v8_stats') 
    inv1 = panel_state.get('inv1'); inv2 = panel_state.get('inv2');
    inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1); inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2);
    title = panel_state.get('title', 'Full Statistics');
    if not stats: return dbc.Alert("Could not load statistics.", color="danger");

    x_lims = panel_state.get('x_lims'); y_lims = panel_state.get('y_lims');
    is_angular_x = inv1 in TORSION_INVARIANTS
    is_angular_y = inv2 in TORSION_INVARIANTS

    def get_stat(key, axis, p=3):
        val = stats.get(f'{key}_{axis}')
        if key in ['mean', 'min', 'max', 'peak']:
            limits = x_lims if axis == 'x' else y_lims
            is_angular = is_angular_x if axis == 'x' else is_angular_y
            val = normalize_angular_stat(val, limits, is_angular)
        return format_stat_value(val, use_sci_notation, precision=p)

    fmt_i = lambda k: f"{stats.get(k, 0):,}" if stats.get(k) is not None else "N/A";

    table_header = [html.Thead(html.Tr([html.Th("Statistic"), html.Th(inv1_label), html.Th(inv2_label)]))]
    table_body = [html.Tbody([
            html.Tr([html.Td("Mean"), html.Td(get_stat('mean', 'x')), html.Td(get_stat('mean', 'y'))]),
            html.Tr([html.Td("Variance"), html.Td(get_stat('variance', 'x')), html.Td(get_stat('variance', 'y'))]),
            # freq_at_mean is likely invalid for 1D, removing
            html.Tr([html.Td("Min"), html.Td(get_stat('min', 'x')), html.Td(get_stat('min', 'y'))]),
            html.Tr([html.Td("Max"), html.Td(get_stat('max', 'x')), html.Td(get_stat('max', 'y'))]),
            # New Stats Added
            html.Tr([html.Td("Peak Loc"), html.Td(get_stat('peak', 'x')), html.Td(get_stat('peak', 'y'))]),
            html.Tr([html.Td("Freq. at Peak"), html.Td(fmt_i('peak_freq_x')), html.Td(fmt_i('peak_freq_y'))]),
            html.Tr([html.Td("R-Value"), html.Td(get_stat('R', 'x')), html.Td(get_stat('R', 'y'))]),
            html.Tr([html.Td("Bin Size"), html.Td(get_stat('bin', 'x')), html.Td(get_stat('bin', 'y'))]),
            html.Tr([html.Td("Window"), html.Td(get_stat('win', 'x')), html.Td(get_stat('win', 'y'))]),
        ])]
        
    peak_x_str = get_stat('peak', 'x', p=2)
    peak_y_str = get_stat('peak', 'y', p=2)

    pairwise_items = [
        dbc.ListGroupItem(f"# of Data Points: {fmt_i('population')}"),
    ]
    
    if stats.get('pearson_correlation') is not None:
         pairwise_items.append(
             dbc.ListGroupItem(f"Covariance: {format_stat_value(stats.get('covariance'), use_sci_notation, precision=3)}")
         )
         pairwise_items.append(
             dbc.ListGroupItem(f"Pearson's (ρ): {format_stat_value(stats.get('pearson_correlation'), use_sci_notation, precision=4)}")
         )
         pairwise_items.extend([
            dbc.ListGroupItem(f"Peak Location (X, Y): ({peak_x_str}, {peak_y_str})"),
            dbc.ListGroupItem(f"Peak Frequency: {fmt_i('peak_freq')}"),
        ])
    else:
         pairwise_items.append(dbc.ListGroupItem("Pairwise Stats: Not available for this combination"))

    pair_stats = dbc.ListGroup(pairwise_items, flush=True, className="mt-3")
    
    layout = [
        dbc.Row([dbc.Col(html.H4(title), width=12)], className="mb-3"),
        dbc.Table(table_header + table_body, bordered=True, striped=True, hover=True, size="sm"),
        html.H5("Pairwise Stats", className="mt-4"), pair_stats
    ]
    return html.Div(layout, className="stats-table-modal p-3")

def build_graph_content(panel_state, log_scale, colormap, uirevision_key, use_sci_notation=False):
    job_type = panel_state.get('job_type')
    current_view = panel_state.get('view')
    title = panel_state.get('title')
    inv1 = panel_state.get('inv1'); inv2 = panel_state.get('inv2');

    if not job_type and panel_state.get('error'):
        return [html.Div([html.I(className="bi bi-exclamation-triangle-fill text-warning"), html.P(panel_state['error'], className="text-center small mt-2")], className="d-flex flex-column h-100 justify-content-center align-items.center placeholder-panel active")], None;

    if job_type == '3D_HEATMAP':
        if current_view == 'stats':
            content = create_combined_stats_table(panel_state, use_sci_notation)
            return [content], None
        
        stats_v6_overlay_data = panel_state.get('stats', {})
        stats_overlay_element = build_3d_stats_overlay(stats_v6_overlay_data)
        figure_data = panel_state.get('figure_data')
        
        if not figure_data:
            return [html.Div([html.I(className="bi bi-exclamation-triangle-fill text-warning"), html.P("No 3D data found.", className="text-center small mt-2")], className="d-flex flex-column h-100 justify-content-center align-items.center placeholder-panel active")], stats_overlay_element;
        
        fig = create_3D_figure(figure_data, title, uirevision_key, log_scale, colormap, inv1, inv2, panel_state.get('x_lims'), panel_state.get('y_lims'));
        content = dcc.Graph(figure=fig, style={'height': '100%'}, className="graph-item");
        return [content], stats_overlay_element;

    elif job_type == '1D_HISTO_VS_STATS' or job_type == '1D_STATS_VS_HISTO':
        if current_view == 'graph':
            histo_data = panel_state.get('figure_data_histo')
            # If no histogram data, we can still show an empty graph or a message
            histo_inv = inv1 if job_type == '1D_HISTO_VS_STATS' else inv2
            fig = create_1D_histo_figure(histo_data, title, histo_inv, log_scale);
            content = dcc.Graph(figure=fig, style={'height': '100%'}, className="graph-item");
            return [content], None
        
        content = create_combined_stats_table(panel_state, use_sci_notation)
        return [content], None;

    elif job_type == '1D_STATS_VS_STATS':
        content = create_combined_stats_table(panel_state, use_sci_notation)
        return [content], None;

    return [html.Div([html.I(className="bi bi-question-circle-fill text-muted"), html.P(f"Unknown plot type: {job_type}", className="text-center small mt-2")], className="d-flex flex-column h-100 justify-content-center align-items.center placeholder-panel active")], None;

def register_rendering_callbacks(app: Dash):
    @app.callback(
        [Output({'type': 'graph-col', 'index': i}, 'children') for i in range(MAX_GRAPHS)] +
        [Output('status-message-store', 'data', allow_duplicate=True)],
        Input('panel-states-store', 'data'), Input('active-panel-store', 'data'),
        Input('sci-notation-store', 'data'),
        Input('scale-switch', 'value'),
        Input('colormap-dropdown', 'value'),
        State('xaxis-min-input', 'value'), State('xaxis-max-input', 'value'),
        State('yaxis-min-input', 'value'), State('yaxis-max-input', 'value'),
        State('status-message-store', 'data'), prevent_initial_call=True
    )
    def update_all_panels(panel_states_json, active_panel_index, sci_notation_pref, 
                          scale_val, colormap_val, x_min, x_max, y_min, y_max,
                          current_status):
        """ Renders all panels using the original v6 layout structure, applying global visual settings. """
        panel_states = json.loads(panel_states_json or '{}'); outputs = []; status_update = no_update;
        if ctx.triggered_id == 'panel-states-store' and current_status: status_update = "";
        panel_style = {'position': 'relative', 'height': '100%'};
        buttons_style = {'position': 'absolute', 'bottom': '5px', 'right': '5px', 'zIndex': 10, 'display': 'flex', 'gap': '0.25rem'};

        # Global Visual Settings
        global_log_scale = scale_val if scale_val is not None else True
        global_colormap = colormap_val if colormap_val else 'Custom Rainbow'
        global_x_lims = [x_min, x_max]
        global_y_lims = [y_min, y_max]

        for i in range(MAX_GRAPHS):
            state = panel_states.get(str(i)); is_active = (i == active_panel_index);
            
            # Apply Globals to the state copy for rendering
            if state:
                state['log_scale'] = global_log_scale
                state['colormap'] = global_colormap
                state['x_lims'] = global_x_lims
                state['y_lims'] = global_y_lims

            job_type = state.get('job_type') if state else None;
            current_view = state.get('view') if state else None

            has_content = bool(state and not state.get('error'))
            can_focus_download = has_content
            
            flipper_button = None
            if current_view == 'graph':
                flipper_button = dbc.Button(
                    html.I(className="bi bi-table"),
                    id={'type': 'toggle-view-button', 'index': i}, 
                    size="sm", title="Switch to Stats View"
                )
            elif current_view == 'stats':
                if job_type == '3D_HEATMAP':
                    icon_class = "bi bi-box"
                    title = "Switch to 3D View"
                elif job_type == '1D_STATS_VS_STATS':
                    icon_class = "bi bi-table"
                    title = "Stats View"
                else:
                    icon_class = "bi bi-bar-chart-line"
                    title = "Switch to Histogram View"
                
                # Disable flipper if purely stats only
                flipper_button = dbc.Button(
                    html.I(className=icon_class), 
                    id={'type': 'toggle-view-button', 'index': i}, 
                    size="sm", title=title,
                    disabled=(job_type == '1D_STATS_VS_STATS') 
                )
            
            button_list = []
            if flipper_button:
                button_list.append(flipper_button)
            
            button_list.extend([
                dbc.Button(html.I(className="bi bi-box-arrow-up-right"), id={'type': 'focus-button', 'index': i}, size="sm", title="Focus", disabled=not can_focus_download),
                dbc.Button(html.I(className="bi bi-download"), id={'type': 'download-button', 'index': i}, size="sm", title="Download", disabled=not can_focus_download),
                dbc.Button(html.I(className="bi bi-gear-fill"), id={'type': 'config-button', 'index': i}, size="sm", color="primary" if is_active else "secondary", title="Configure"),
                dbc.Button(html.I(className="bi bi-x-lg"), id={'type': 'clear-button', 'index': i}, size="sm", color="danger", title="Clear", disabled=not state),
            ])
            
            buttons = html.Div(button_list, style=buttons_style)

            main_content = None; stats_overlay = None;
            try:
                if not state:
                    main_content = html.Div(
                        html.I(className="bi bi-plus-lg"),
                        id={'type': 'placeholder-button', 'index': i},
                        className=f"placeholder-panel d-flex h-100 justify-content-center align-items-center {'placeholder-active' if is_active else ''}"
                    )
                else:
                    # Pass Globals Explicitly
                    content_children, stats_overlay_element = build_graph_content(
                        state, global_log_scale, global_colormap, state.get('uirevision_key', str(i)), sci_notation_pref
                    );
                    main_content = content_children[0];
                    stats_overlay = stats_overlay_element;

            except Exception as e:
                print(f"ERROR during panel rendering (index {i}): {e}"); import traceback; traceback.print_exc();
                main_content = html.Div([html.I(className="bi bi-exclamation-octagon-fill text-danger"), html.P(f"Rendering Error: {e}", className="text-center small mt-2")], className="d-flex flex-column h-100 justify-content-center align-items-center placeholder-panel active");

            panel_children = [buttons, main_content];
            if stats_overlay and current_view == 'graph':
                panel_children.append(stats_overlay);
                
            outputs.append(html.Div(panel_children, style=panel_style));

        return outputs + [status_update];