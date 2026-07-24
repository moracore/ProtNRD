import json
import numpy as np
from scipy.ndimage import binary_dilation, maximum_filter
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
import figure_cache
from ..constants import (
    INVARIANT_AXIS_LABEL, N_RAINBOW, MAX_GRAPHS, TORSION_INVARIANTS
)
import math

# --- Helper for safe formatting ---
def safe_format_int(value):
    """Safely formats an integer with commas, handling None/Nulls."""
    if value is None:
        return "N/A"
    try:
        # Ensure it's treated as a number before formatting
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)

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
            s = f"{value:.{precision}f}"
            return s.rstrip('0').rstrip('.') if '.' in s else s
    except Exception:
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
            xaxis_title=INVARIANT_AXIS_LABEL.get(inv_name, inv_name),
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
        xaxis_title=INVARIANT_AXIS_LABEL.get(inv_name, inv_name),
        yaxis_title="Count",
        yaxis_type="log" if log_scale else "linear",
        margin=dict(l=20, r=20, b=30, t=40),
        uirevision=title
    )
    return fig

EDGE_EPS = 1e-6  # near-zero value placed on empty cells touching real data, purely so an
                 # isolated bin has finite neighbours to span a Surface face

def _scaffold_edges(z, inv_row, inv_col, eps=EDGE_EPS):
    """Make isolated/sparse bins renderable WITHOUT changing any real count: each empty cell
    that touches a populated cell (8-neighbour) is set to a near-zero `eps`, just so a lone
    count=1 bin has finite neighbours to span a Surface quad. Real counts stay exact and
    far-from-data empties stay 0 -> NaN -> transparent. The eps rim sits at the floor (height
    ~0, lowest colour). Periodic τ torsion axes wrap; others don't. z: axis0->inv_row, axis1->inv_col."""
    if z.ndim != 2 or z.size == 0:
        return z
    mask = z > 0
    if not mask.any():
        return z
    m = np.pad(mask, ((1, 1), (0, 0)), mode='wrap' if inv_row in ('tau_NA', 'tau_AC', 'tau_CN') else 'constant')
    m = np.pad(m, ((0, 0), (1, 1)), mode='wrap' if inv_col in ('tau_NA', 'tau_AC', 'tau_CN') else 'constant')
    edge = binary_dilation(m, structure=np.ones((3, 3), bool))[1:-1, 1:-1] & ~mask
    out = z.astype(float, copy=True)
    out[edge] = eps
    return out

def create_3D_figure(grid, title, uirevision_key, log_scale, colormap, inv1_name=None, inv2_name=None, x_lims=None, y_lims=None, smooth=True):
    def get_invariant_type(inv_name):
        if not inv_name: return 'unknown'
        if inv_name in ['tau_NA', 'tau_AC', 'tau_CN', 'angle_N', 'angle_A', 'angle_C']: return 'angular'
        if 'length' in inv_name: return 'length'
        return 'unknown'

    def _get_axis_range(inv_name):
        if inv_name == 'tau_CN': return [-90, 270]
        inv_type = get_invariant_type(inv_name)
        if inv_type == 'angular': return [-180, 180]
        if inv_type == 'length': return [1, 2]
        return None

    if not grid:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (No Data)", margin=dict(l=0, r=0, b=0, t=40))
        return fig

    original_x_data = grid['x']
    original_y_data = grid['y']
    original_z_data = grid['z']

    if original_z_data.size == 0 or original_x_data.size == 0 or original_y_data.size == 0 or original_z_data.ndim != 2:
        fig = go.Figure()
        fig.update_layout(title=f"{title} (No Data)", margin=dict(l=0, r=0, b=0, t=40))
        return fig

    # Scaffold a near-zero rim around populated bins so isolated/sparse bins render (counts
    # untouched). Toggled by the global switch. Grid axes: axis0 -> inv2 (rows), axis1 -> inv1 (cols).
    if smooth:
        original_z_data = _scaffold_edges(original_z_data, inv2_name, inv1_name)

    z_axis_title = "Log(Count + 1)" if log_scale else "Count"
    # Force an equal-sided cube. Without this Plotly's default 'auto' aspect makes each axis
    # proportional to its data range, so once counts reach 1e5-1e7 (e.g. the aggregated "all"
    # DB) the Count axis dwarfs the +/-180 angle axes and the surface collapses to a speck.
    scene_config = {'zaxis_title': z_axis_title, 'aspectmode': 'cube', 'camera': dict(eye=dict(x=-1.5, y=-2.5, z=1.5))}
    cycle_range = 360
    
    # Init tiles
    x_tile_range, y_tile_range = [0], [0]

    # --- AXIS CONFIGURATION ---
    # Map Inv1 to Y-axis, Inv2 to X-axis
    for axis, inv_name, original_axis_data, limits in [('yaxis', inv1_name, original_x_data, x_lims), ('xaxis', inv2_name, original_y_data, y_lims)]:
        scene_config[axis] = {'title': INVARIANT_AXIS_LABEL.get(inv_name, inv_name or axis[0].upper())}
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
                
                tick_step = next((s for s in (5, 10, 15, 30, 45, 90, 180) if (max_lim - min_lim) / s <= 6), 180)
                start_tick = math.ceil(min_lim / tick_step) * tick_step
                tickvals = [t for t in range(start_tick, int(max_lim) + 1, tick_step)]
                ticktext = [str(v) for v in tickvals]
                scene_config[axis]['tickvals'] = tickvals
                scene_config[axis]['ticktext'] = ticktext

    # --- DATA GENERATION & TILING ---
    if len(x_tile_range) > 1 or len(y_tile_range) > 1:
        # Screen X comes from Inv2 (original_y) + x_tile_range
        final_x_data = np.concatenate([original_y_data + offset for offset in x_tile_range])

        # Screen Y comes from Inv1 (original_x) + y_tile_range
        final_y_data = np.concatenate([original_x_data + offset for offset in y_tile_range])

        # Z Matrix Transposition
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
        # Empty bins -> NaN: transparent floor (drawn as nothing), no white, no alpha so
        # depth stays correct. Sparse cells are kept renderable by _scaffold_edges above.
        z_processed = final_z_data.astype(float)
        z_processed[z_processed == 0] = np.nan

    finite_z_original = original_z_data.astype(float)
    finite_z_original = finite_z_original[np.isfinite(finite_z_original) & (finite_z_original > 0)]
    z_display_values = np.log10(z_processed + 1) if log_scale else z_processed
    # Display the eps scaffold rim (0 < count < 1) flat at 0 so the 1e-6 never shows up as
    # height or in the hover readout; real integer counts (>=1) and NaN empties are untouched.
    rim = (z_processed > 0) & (z_processed < 1)
    z_display_values = np.where(rim, 0.0, z_display_values)
    # Colour the rim with its neighbouring real count (not its ~0 value) so an isolated spike
    # is one solid colour over its whole height instead of fading to blue at the base.
    color_count = z_processed
    if rim.any():
        neigh_max = maximum_filter(np.where(z_processed >= 1, z_processed, 0.0), size=3, mode='constant', cval=0.0)
        color_count = np.where(rim, neigh_max, z_processed)
    color_values = np.log10(color_count + 1e-9)
    cmin_val, cmax_val = (0, 1)
    if finite_z_original.size > 0:
        cmin_val = np.log10(1)
        cmax_val = np.log10(np.max(finite_z_original) + 1)

    cs = N_RAINBOW if colormap == "Custom Rainbow" else colormap
    # Surface hover is skipped (go.Surface has no per-cell hover control, so it would tag
    # 'z: NaN' over the transparent empty cells). Hover lives on an invisible point layer at
    # the real bins only (below), giving a clean count readout with no NaN/empty tags.
    traces = [go.Surface(x=final_x_data, y=final_y_data, z=z_display_values, surfacecolor=color_values,
        colorscale=cs, showscale=False, cmin=cmin_val, cmax=cmax_val, hoverinfo='skip',
        lighting=dict(ambient=0.8, diffuse=1, specular=0.2))]
    # WebGL hard limit: ~30M vertices. Each Scatter3d marker costs ~700 vertices,
    # so cap at 5000 points (3.5M vertices) to stay well clear. Keep the highest-
    # count bins — those are the bins users actually hover on.
    _MAX_HOVER = 5000
    real_mask = np.isfinite(z_processed) & (z_processed >= 1)
    if real_mask.any():
        ry, rx = np.where(real_mask)
        counts = z_processed[ry, rx]
        if len(counts) > _MAX_HOVER:
            top = np.argpartition(counts, -_MAX_HOVER)[-_MAX_HOVER:]
            ry, rx, counts = ry[top], rx[top], counts[top]
        xlabel = INVARIANT_AXIS_LABEL.get(inv2_name, 'X')  # screen X = Inv2
        ylabel = INVARIANT_AXIS_LABEL.get(inv1_name, 'Y')  # screen Y = Inv1
        traces.append(go.Scatter3d(
            x=final_x_data[rx], y=final_y_data[ry], z=z_display_values[ry, rx], mode='markers',
            marker=dict(size=4, color='rgba(0,0,0,0)'),  # invisible, but still hoverable
            customdata=counts.astype(int),
            hovertemplate=f"{xlabel}: %{{x:.3g}}<br>{ylabel}: %{{y:.3g}}<br>Count: %{{customdata}}<extra></extra>",
            showlegend=False))
    fig = go.Figure(data=traces)
    fig.update_layout(title=title, uirevision=uirevision_key, scene=scene_config, margin=dict(l=0, r=0, b=0, t=40))
    return fig

def build_3d_stats_overlay(stats_data):
    if not stats_data: return None
    pop = stats_data.get('population', 0); peak_x = stats_data.get('peak_x'); peak_y = stats_data.get('peak_y');
    
    peak_str = "Peak: N/A"
    if isinstance(peak_x, (int, float)) and isinstance(peak_y, (int, float)):
        peak_str = f"Peak: ({peak_x:.1f}, {peak_y:.1f})"

    return html.Div([
        html.P(f"# {safe_format_int(pop)}", title="Total Data Points"),
        html.P(peak_str, title="Peak Location"),
        html.P(f"▲ {safe_format_int(stats_data.get('peak_freq', 0))}", title="Peak Count")
    ], className="stats-overlay")

def create_combined_stats_table(panel_state, use_sci_notation=False):
    """
    Creates the compact stats table for the main graph view.
    """
    stats = panel_state.get('full_v8_stats', {})
    if not stats:
        return dbc.Card(dbc.CardBody("No stats data available."), className="stat-card h-100 w-100")

    inv1 = panel_state.get('inv1'); inv2 = panel_state.get('inv2');
    inv1_label = INVARIANT_AXIS_LABEL.get(inv1, inv1); inv2_label = INVARIANT_AXIS_LABEL.get(inv2, inv2);
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

    table_style = dict(bordered=True, striped=True, hover=True, size="sm")

    table_header = html.Thead(html.Tr([
        html.Th("Statistic"), html.Th(inv1_label), html.Th(inv2_label)
    ]))
    
    table_body = html.Tbody([
        html.Tr([html.Td("Mean"), html.Td(get_stat('mean', 'x')), html.Td(get_stat('mean', 'y'))]),
        html.Tr([html.Td("Variance"), html.Td(get_stat('variance', 'x')), html.Td(get_stat('variance', 'y'))]),
        html.Tr([html.Td("Peak Loc"), html.Td(get_stat('peak', 'x')), html.Td(get_stat('peak', 'y'))]),
        html.Tr([html.Td("Freq. at Peak"), html.Td(safe_format_int(stats.get('peak_freq_x'))), html.Td(safe_format_int(stats.get('peak_freq_y')))]),
    ])
    comparison_table = dbc.Table([table_header, table_body], **table_style, className="mb-3")
    
    peak_x_str = get_stat('peak', 'x', p=2)
    peak_y_str = get_stat('peak', 'y', p=2)
    
    pairwise_rows = [
        html.Tr([html.Td("# of Data Points"), html.Td(safe_format_int(stats.get('population')))]),
    ]
    
    if stats.get('pearson_correlation') is not None:
        pairwise_rows.extend([
            html.Tr([html.Td("Peak Location"), html.Td(f"({peak_x_str}, {peak_y_str})")]),
            html.Tr([html.Td("Peak Count"), html.Td(safe_format_int(stats.get('peak_freq')))]),
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
    ], className="stat-card h-100 w-100", style={'overflowY': 'auto'})

def build_full_stats_table(panel_state, use_sci_notation=False):
    """
    Creates the Full Stats table for the 'Stats View'.
    """
    stats = panel_state.get('full_v8_stats') 
    inv1 = panel_state.get('inv1'); inv2 = panel_state.get('inv2');
    inv1_label = INVARIANT_AXIS_LABEL.get(inv1, inv1); inv2_label = INVARIANT_AXIS_LABEL.get(inv2, inv2);
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

    table_header = [html.Thead(html.Tr([html.Th("Statistic"), html.Th(inv1_label), html.Th(inv2_label)]))]
    
    table_body = [html.Tbody([
            html.Tr([html.Td("Mean"), html.Td(get_stat('mean', 'x')), html.Td(get_stat('mean', 'y'))]),
            html.Tr([html.Td("Variance"), html.Td(get_stat('variance', 'x')), html.Td(get_stat('variance', 'y'))]),
            html.Tr([html.Td("Peak Loc"), html.Td(get_stat('peak', 'x')), html.Td(get_stat('peak', 'y'))]),
            html.Tr([html.Td("Freq. at Peak"), html.Td(safe_format_int(stats.get('peak_freq_x'))), html.Td(safe_format_int(stats.get('peak_freq_y')))]),
            html.Tr([html.Td("R-Value"), html.Td(get_stat('R', 'x')), html.Td(get_stat('R', 'y'))]),
            html.Tr([html.Td("Bin Size"), html.Td(get_stat('bin', 'x')), html.Td(get_stat('bin', 'y'))]),
            html.Tr([html.Td("Window"), html.Td(get_stat('win', 'x')), html.Td(get_stat('win', 'y'))]),
        ])]
        
    peak_x_str = get_stat('peak', 'x', p=2)
    peak_y_str = get_stat('peak', 'y', p=2)

    pairwise_items = [
        dbc.ListGroupItem(f"# of Data Points: {safe_format_int(stats.get('population'))}"),
    ]
    
    if stats.get('pearson_correlation') is not None:
         pairwise_items.extend([
            dbc.ListGroupItem(f"Peak Location (X, Y): ({peak_x_str}, {peak_y_str})"),
            dbc.ListGroupItem(f"Peak Count: {safe_format_int(stats.get('peak_freq'))}"),
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

def build_graph_content(panel_state, log_scale, colormap, uirevision_key, use_sci_notation=False, smooth=True):
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
        _gk = (panel_state.get('plot_key'), panel_state.get('inv1'), panel_state.get('db_choice'))
        grid = figure_cache.get(_gk)

        if not grid:
            return [html.Div([html.I(className="bi bi-exclamation-triangle-fill text-warning"), html.P("No 3D data found.", className="text-center small mt-2")], className="d-flex flex-column h-100 justify-content-center align-items.center placeholder-panel active")], stats_overlay_element;

        _fk = figure_cache.make_fig_key(_gk, log_scale, smooth, colormap, panel_state.get('x_lims'), panel_state.get('y_lims'))
        fig = figure_cache.get_fig(_fk)
        if fig is None:
            fig = create_3D_figure(grid, title, uirevision_key, log_scale, colormap, inv1, inv2, panel_state.get('x_lims'), panel_state.get('y_lims'), smooth=smooth)
            figure_cache.put_fig(_fk, fig)
        content = dcc.Graph(figure=fig, style={'height': '100%'}, className="graph-item");
        return [content], stats_overlay_element;

    elif job_type == '1D_HISTO_VS_STATS' or job_type == '1D_STATS_VS_HISTO':
        if current_view == 'graph':
            histo_data = panel_state.get('figure_data_histo')
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
        Input('smooth-switch', 'value'),
        Input('colormap-dropdown', 'value'),
        State('xaxis-min-input', 'value'), State('xaxis-max-input', 'value'),
        State('yaxis-min-input', 'value'), State('yaxis-max-input', 'value'),
        State('status-message-store', 'data'), prevent_initial_call=True
    )
    def update_all_panels(panel_states_json, active_panel_index, sci_notation_pref,
                          scale_val, smooth_val, colormap_val, x_min, x_max, y_min, y_max,
                          current_status):
        """ Renders all panels. Scale/smoothing are global (all panels); colormap/limits are per active panel. """
        panel_states = json.loads(panel_states_json or '{}')
        global_log_scale = bool(scale_val)
        global_smooth = bool(smooth_val)
        outputs = []
        status_update = no_update
        if ctx.triggered_id == 'panel-states-store' and current_status: status_update = ""
        
        panel_style = 'graph-item'

        for i in range(MAX_GRAPHS):
            state = panel_states.get(str(i))
            is_active = (i == active_panel_index)
            
            # --- COLORMAP / AXIS LIMITS ARE PER-PANEL (apply to ACTIVE panel only) ---
            # Scale is a GLOBAL setting (see scale-switch in Global Options) and is
            # applied to every panel uniformly below via `global_log_scale`.
            if state:
                if is_active:
                    state['colormap'] = colormap_val if colormap_val else 'Custom Rainbow'
                    state['x_lims'] = [x_min, x_max]
                    state['y_lims'] = [y_min, y_max]

                job_type = state.get('job_type') if state else None
            current_view = state.get('view') if state else None

            # Empty panel — render placeholder only, no buttons
            if not state:
                outputs.append(html.Div(
                    html.Div(
                        html.I(className="bi bi-plus-lg"),
                        id={'type': 'placeholder-button', 'index': i},
                        className="placeholder-panel d-flex h-100 justify-content-center align-items-center"
                    ),
                    className=panel_style
                ))
                continue

            has_content = not state.get('error')
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
                    btn_title = "Switch to 3D View"
                elif job_type == '1D_STATS_VS_STATS':
                    icon_class = "bi bi-table"
                    btn_title = "Stats View"
                else:
                    icon_class = "bi bi-bar-chart-line"
                    btn_title = "Switch to Histogram View"
                flipper_button = dbc.Button(
                    html.I(className=icon_class),
                    id={'type': 'toggle-view-button', 'index': i},
                    size="sm", title=btn_title,
                    disabled=(job_type == '1D_STATS_VS_STATS')
                )

            button_list = []
            if flipper_button:
                button_list.append(flipper_button)
            button_list.extend([
                dbc.Button(html.I(className="bi bi-box-arrow-up-right"), id={'type': 'focus-button', 'index': i}, size="sm", title="Focus", disabled=not can_focus_download),
                dbc.Button(html.I(className="bi bi-download"), id={'type': 'download-button', 'index': i}, size="sm", title="Download", disabled=not can_focus_download),
                dbc.Button(html.I(className="bi bi-gear-fill"), id={'type': 'config-button', 'index': i}, size="sm", color="primary" if is_active else "secondary", title="Configure"),
                dbc.Button(html.I(className="bi bi-x-lg"), id={'type': 'clear-button', 'index': i}, size="sm", color="danger", title="Clear"),
            ])
            buttons = html.Div(button_list, style={'position': 'absolute', 'bottom': '10px', 'right': '10px', 'zIndex': 10, 'display': 'flex', 'gap': '0.25rem'})

            stats_overlay = None
            try:
                content_children, stats_overlay_element = build_graph_content(
                    state,
                    global_log_scale,
                    state.get('colormap', 'Custom Rainbow'),
                    state.get('uirevision_key', str(i)),
                    sci_notation_pref,
                    smooth=global_smooth
                )
                main_content = content_children[0]
                stats_overlay = stats_overlay_element
            except Exception as e:
                print(f"ERROR during panel rendering (index {i}): {e}")
                main_content = html.Div(
                    [html.I(className="bi bi-exclamation-octagon-fill text-danger"),
                     html.P(f"Rendering Error: {e}", className="text-center small mt-2")],
                    className="d-flex flex-column h-100 justify-content-center align-items-center placeholder-panel active"
                )

            panel_children = [main_content, buttons]
            if stats_overlay and current_view == 'graph':
                panel_children.append(stats_overlay)
            outputs.append(html.Div(panel_children, className=panel_style))

        return outputs + [status_update]