import math
import numpy as np
from scipy.ndimage import binary_dilation, maximum_filter
import plotly.graph_objects as go
from dash import dcc, html
import dash_bootstrap_components as dbc
from ..constants import INVARIANT_SHORTHAND, INVARIANT_AXIS_LABEL, N_RAINBOW, TORSION_INVARIANTS


def format_stat_value(value, use_sci_notation=False, precision=3):
    if value is None: return "N/A"
    try:
        if use_sci_notation: return f"{value:.{precision}e}"
        else:
            if abs(value) < 1e-3 and abs(value) > 0: return f"{value:.{precision}e}"
            s = f"{value:.{precision}f}"
            return s.rstrip('0').rstrip('.') if '.' in s else s
    except (TypeError, ValueError): return str(value)


def normalize_angular_stat(value, limits, is_angular):
    if not is_angular or value is None: return value
    try:
        min_lim, max_lim = limits
        if min_lim is None or max_lim is None: return value
    except: return value
    if min_lim < max_lim:
        if min_lim <= value <= max_lim: return value
        if min_lim <= value + 360 <= max_lim: return value + 360
        if min_lim <= value - 360 <= max_lim: return value - 360
    return value


def create_1D_histo_figure(data, title, inv_name, log_scale):
    if not data:
        fig = go.Figure(); fig.update_layout(title=f"{title} (No Histogram Data)", margin=dict(l=0, r=0, b=0, t=40)); return fig
    fig = go.Figure(data=[go.Bar(x=data.get('bins', []), y=data.get('counts', []), marker_color='#003E7C')])
    fig.update_layout(
        title=title, xaxis_title=INVARIANT_AXIS_LABEL.get(inv_name, inv_name), yaxis_title="Count",
        yaxis_type="log" if log_scale else "linear", margin=dict(l=20, r=20, b=30, t=40), uirevision=title
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
        t = get_invariant_type(inv_name)
        if t == 'angular': return [-180, 180]
        if t == 'length': return [1, 2]
        return None

    if not grid:
        fig = go.Figure(); fig.update_layout(title=f"{title} (No Data)", margin=dict(l=0, r=0, b=0, t=40)); return fig

    original_x_data = grid['x']
    original_y_data = grid['y']
    original_z_data = grid['z']

    if original_z_data.size == 0 or original_x_data.size == 0 or original_y_data.size == 0 or original_z_data.ndim != 2:
        fig = go.Figure(); fig.update_layout(title=f"{title} (No Data)", margin=dict(l=0, r=0, b=0, t=40)); return fig

    # Scaffold a near-zero rim around populated bins so isolated/sparse bins render (counts
    # untouched). Toggled by the global switch. Grid axes: axis0 -> inv2 (rows), axis1 -> inv1 (cols).
    if smooth:
        original_z_data = _scaffold_edges(original_z_data, inv2_name, inv1_name)

    z_title = "Log(Count + 1)" if log_scale else "Count"
    # Force an equal-sided cube. Without this Plotly's default 'auto' aspect makes each axis
    # proportional to its data range, so once counts reach 1e5-1e7 (e.g. the aggregated "all"
    # DB) the Count axis dwarfs the +/-180 angle axes and the surface collapses to a speck.
    scene = {'zaxis_title': z_title, 'aspectmode': 'cube', 'camera': dict(eye=dict(x=-1.5, y=-2.5, z=1.5))}
    final_x, final_y, final_z = original_x_data.copy(), original_y_data.copy(), original_z_data.copy()
    x_tiles, y_tiles = [0], [0]

    for axis, inv, orig_data, lims in [('xaxis', inv1_name, original_x_data, x_lims), ('yaxis', inv2_name, original_y_data, y_lims)]:
        scene[axis] = {'title': INVARIANT_AXIS_LABEL.get(inv, inv or axis[0].upper())}
        is_ang = get_invariant_type(inv) == 'angular'
        curr_lims = lims if (lims and lims[0] is not None and lims[1] is not None and lims[0] < lims[1]) else _get_axis_range(inv)
        min_l, max_l = curr_lims if curr_lims else (None, None)
        if min_l is not None and max_l is not None:
            scene[axis]['range'] = [min_l, max_l]
            if is_ang and orig_data.size > 0:
                d_min = orig_data.min(); c_min, c_max = math.floor((min_l - d_min) / 360), math.ceil((max_l - d_min) / 360)
                tiles = [i * 360 for i in range(c_min - 1, c_max + 1)]
                if axis == 'xaxis': x_tiles = tiles
                else: y_tiles = tiles
                t_span = max_l - min_l
                t_step = next((s for s in (5, 10, 15, 30, 45, 90, 180) if t_span / s <= 6), 180)
                ticks = [t for t in range(math.ceil(min_l/t_step)*t_step, int(max_l)+1, t_step)]
                scene[axis]['tickvals'] = ticks; scene[axis]['ticktext'] = [str(v) for v in ticks]

    if len(x_tiles) > 1 or len(y_tiles) > 1:
        final_x = np.concatenate([original_x_data + o for o in x_tiles])
        final_y = np.concatenate([original_y_data + o for o in y_tiles])
        final_z = np.tile(original_z_data, (len(y_tiles), len(x_tiles)))
        sx = np.argsort(final_x); final_x = final_x[sx]; final_z = final_z[:, sx]
        sy = np.argsort(final_y); final_y = final_y[sy]; final_z = final_z[sy, :]

    # Empty bins -> NaN: transparent floor (drawn as nothing), no white, no alpha so depth
    # stays correct. Sparse cells are kept renderable by _scaffold_edges above.
    z_proc = final_z.astype(float)
    z_proc[z_proc == 0] = np.nan
    z_disp = np.log10(z_proc + 1) if log_scale else z_proc
    # Display the eps scaffold rim (0 < count < 1) flat at 0 so the 1e-6 never shows up as
    # height or in the hover readout; real integer counts (>=1) and NaN empties are untouched.
    rim = (z_proc > 0) & (z_proc < 1)
    z_disp = np.where(rim, 0.0, z_disp)
    # Colour the rim with its neighbouring real count so an isolated spike is one solid colour
    # over its whole height instead of fading to blue at the base.
    color_count = z_proc
    if rim.any():
        neigh_max = maximum_filter(np.where(z_proc >= 1, z_proc, 0.0), size=3, mode='constant', cval=0.0)
        color_count = np.where(rim, neigh_max, z_proc)
    color_v = np.log10(color_count + 1e-9)
    real = np.isfinite(z_proc) & (z_proc >= 1)  # exclude the eps scaffold rim from the colour scale
    cmin_v, cmax_v = (0.0, 1.0)
    if real.any():
        cmin_v = 0.0  # log10(1): lowest real count
        cmax_v = float(np.log10(np.nanmax(z_proc[real]) + 1))
        if cmax_v <= cmin_v: cmax_v = cmin_v + 1.0

    cs = N_RAINBOW if colormap == "Custom Rainbow" else colormap
    # Surface hover is skipped (go.Surface has no per-cell hover control, so it would tag
    # 'z: NaN' over the transparent empty cells). Hover lives on an invisible point layer at
    # the real bins only (below), giving a clean count readout with no NaN/empty tags.
    traces = [go.Surface(
        x=final_x, y=final_y, z=z_disp, surfacecolor=color_v, cmin=cmin_v, cmax=cmax_v,
        colorscale=cs, showscale=False, hoverinfo='skip',
        lighting=dict(ambient=0.8, diffuse=1, specular=0.2)
    )]
    # WebGL hard limit: ~30M vertices. Each Scatter3d marker costs ~700 vertices,
    # so cap at 5000 points (3.5M vertices) to stay well clear. Keep the highest-
    # count bins — those are the bins users actually hover on.
    _MAX_HOVER = 5000
    real_mask = np.isfinite(z_proc) & (z_proc >= 1)
    if real_mask.any():
        ry, rx = np.where(real_mask)
        counts = z_proc[ry, rx]
        if len(counts) > _MAX_HOVER:
            top = np.argpartition(counts, -_MAX_HOVER)[-_MAX_HOVER:]
            ry, rx, counts = ry[top], rx[top], counts[top]
        xlabel = INVARIANT_AXIS_LABEL.get(inv1_name, 'X')  # screen X = Inv1
        ylabel = INVARIANT_AXIS_LABEL.get(inv2_name, 'Y')  # screen Y = Inv2
        traces.append(go.Scatter3d(
            x=final_x[rx], y=final_y[ry], z=z_disp[ry, rx], mode='markers',
            marker=dict(size=4, color='rgba(0,0,0,0)'),  # invisible, but still hoverable
            customdata=counts.astype(int),
            hovertemplate=f"{xlabel}: %{{x:.3g}}<br>{ylabel}: %{{y:.3g}}<br>Count: %{{customdata}}<extra></extra>",
            showlegend=False))
    fig = go.Figure(data=traces)
    fig.update_layout(title=title, uirevision=uirevision_key, scene=scene, margin=dict(l=0, r=0, b=0, t=40))
    return fig


def create_combined_stats_table(panel_state, use_sci_notation=False):
    stats = panel_state.get('full_v8_stats', {})
    if not stats: return dbc.Card(dbc.CardBody("No stats data available."), className="stat-card h-100 w-100")

    inv1 = panel_state.get('inv1'); inv2 = panel_state.get('inv2');
    inv1_l = INVARIANT_AXIS_LABEL.get(inv1, inv1); inv2_l = INVARIANT_AXIS_LABEL.get(inv2, inv2);
    x_lims = panel_state.get('x_lims'); y_lims = panel_state.get('y_lims');
    is_ang_x = inv1 in TORSION_INVARIANTS; is_ang_y = inv2 in TORSION_INVARIANTS

    def get_stat(key, axis, p=3):
        val = stats.get(f'{key}_{axis}')
        if key in ['mean', 'min', 'median', 'max', 'peak']:
            val = normalize_angular_stat(val, x_lims if axis == 'x' else y_lims, is_ang_x if axis == 'x' else is_ang_y)
        return format_stat_value(val, use_sci_notation, precision=p)

    fmt_i = lambda k: f"{stats.get(k, 0):,}" if stats.get(k) is not None else "N/A"

    body = [
        html.Tr([html.Td("Mean"), html.Td(get_stat('mean', 'x')), html.Td(get_stat('mean', 'y'))]),
        html.Tr([html.Td("Variance"), html.Td(get_stat('variance', 'x')), html.Td(get_stat('variance', 'y'))]),
        html.Tr([html.Td("Count at Mean"), html.Td(fmt_i('freq_at_mean_x')), html.Td(fmt_i('freq_at_mean_y'))]),
    ]
    comp_tbl = dbc.Table([html.Thead(html.Tr([html.Th("Statistic"), html.Th(inv1_l), html.Th(inv2_l)])), html.Tbody(body)], bordered=True, striped=True, hover=True, size="sm", className="mb-3")

    pair_body = html.Tbody([
        html.Tr([html.Td("# of Data Points"), html.Td(fmt_i('population'))]),
        html.Tr([html.Td("Peak Location"), html.Td(f"({get_stat('peak', 'x', 2)}, {get_stat('peak', 'y', 2)})")]),
        html.Tr([html.Td("Peak Count"), html.Td(fmt_i('peak_freq'))]),
    ])
    pair_tbl = dbc.Table(pair_body, bordered=True, striped=True, hover=True, size="sm")

    return dbc.Card([
        dbc.CardHeader(panel_state.get('title', 'Statistics')),
        dbc.CardBody([html.H5("Comparison", className="card-subtitle mb-2 text-muted"), comp_tbl, html.H5("Pairwise", className="card-subtitle mb-2 mt-3 text-muted"), pair_tbl], className="p-3")
    ], className="stat-card h-100 w-100", style={'overflowY': 'auto'})


def build_full_stats_table(panel_state, use_sci_notation=False):
    return create_combined_stats_table(panel_state, use_sci_notation)
