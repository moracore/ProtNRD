import math
import time
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html
import dash_bootstrap_components as dbc
from ..constants import INVARIANT_SHORTHAND, N_RAINBOW, TORSION_INVARIANTS


def format_stat_value(value, use_sci_notation=False, precision=3):
    if value is None: return "N/A"
    try:
        if use_sci_notation: return f"{value:.{precision}e}"
        else:
            if abs(value) < 1e-3 and abs(value) > 0: return f"{value:.{precision}e}"
            return f"{value:.{precision}f}"
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
        title=title, xaxis_title=INVARIANT_SHORTHAND.get(inv_name, inv_name), yaxis_title="Frequency",
        yaxis_type="log" if log_scale else "linear", margin=dict(l=20, r=20, b=30, t=40), uirevision=str(time.time())
    )
    return fig


def create_3D_figure(data, title, uirevision_key, log_scale, colormap, inv1_name=None, inv2_name=None, x_lims=None, y_lims=None):
    def get_invariant_type(inv_name):
        if not inv_name: return 'unknown'
        if inv_name in ['tau_NA', 'tau_AC', 'tau_CN', 'angle_N', 'angle_A', 'angle_C']: return 'angular'
        if 'length' in inv_name: return 'length'
        return 'unknown'
    def _get_axis_range(inv_name):
        t = get_invariant_type(inv_name)
        if t == 'angular': return [-180, 180]
        if t == 'length': return [1, 2]
        return None

    original_x_data = np.array(data.get('x', [])); original_y_data = np.array(data.get('y', [])); original_z_data = np.array(data.get('z', []))

    if 'points' in data and data.get('points'):
        pts = data.get('points')
        if not pts: original_x_data, original_y_data, original_z_data = np.array([]), np.array([]), np.array([[]])
        else:
            xs, ys, zs = zip(*pts)
            xs, ys, zs = np.array(xs, float), np.array(ys, float), np.array(zs, float)
            x_c, y_c = np.unique(xs), np.unique(ys)
            z_grid = np.zeros((len(y_c), len(x_c)), float)
            x_map, y_map = {v: i for i, v in enumerate(x_c)}, {v: i for i, v in enumerate(y_c)}
            for x, y, z in zip(xs, ys, zs): z_grid[y_map[y], x_map[x]] += float(z)
            original_x_data, original_y_data, original_z_data = x_c, y_c, z_grid

    if original_z_data.size == 0 or original_x_data.size == 0 or original_y_data.size == 0 or original_z_data.ndim != 2:
        fig = go.Figure(); fig.update_layout(title=f"{title} (No Data)", margin=dict(l=0, r=0, b=0, t=40)); return fig

    z_title = "Log(Frequency + 1)" if log_scale else "Frequency"
    scene = {'zaxis_title': z_title, 'camera': dict(eye=dict(x=-1.5, y=-2.5, z=1.5))}
    final_x, final_y, final_z = original_x_data.copy(), original_y_data.copy(), original_z_data.copy()
    x_tiles, y_tiles = [0], [0]

    for axis, inv, orig_data, lims in [('xaxis', inv1_name, original_x_data, x_lims), ('yaxis', inv2_name, original_y_data, y_lims)]:
        scene[axis] = {'title': INVARIANT_SHORTHAND.get(inv, inv or axis[0].upper())}
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
                ticks = [t for t in range(math.ceil(min_l/45)*45, int(max_l)+45, 45)]
                scene[axis]['tickvals'] = ticks; scene[axis]['ticktext'] = [str(v) for v in ticks]

    if len(x_tiles) > 1 or len(y_tiles) > 1:
        final_x = np.concatenate([original_x_data + o for o in x_tiles])
        final_y = np.concatenate([original_y_data + o for o in y_tiles])
        final_z = np.tile(original_z_data, (len(y_tiles), len(x_tiles)))
        sx = np.argsort(final_x); final_x = final_x[sx]; final_z = final_z[:, sx]
        sy = np.argsort(final_y); final_y = final_y[sy]; final_z = final_z[sy, :]

    z_proc = final_z.astype(float)
    z_proc[z_proc == 0] = np.nan
    z_disp = np.log10(z_proc + 1) if log_scale else z_proc
    color_v = np.log10(z_proc + 1e-9)

    fig = go.Figure(data=[go.Surface(
        x=final_x, y=final_y, z=z_disp, surfacecolor=color_v,
        colorscale=N_RAINBOW if colormap == "Custom Rainbow" else colormap, showscale=False,
        lighting=dict(ambient=0.8, diffuse=1, specular=0.2)
    )])
    fig.update_layout(title=title, uirevision=uirevision_key, scene=scene, margin=dict(l=0, r=0, b=0, t=40))
    return fig


def create_combined_stats_table(panel_state, use_sci_notation=False):
    stats = panel_state.get('full_v8_stats', {})
    if not stats: return dbc.Card(dbc.CardBody("No stats data available."), className="stat-card h-100 w-100")

    inv1 = panel_state.get('inv1'); inv2 = panel_state.get('inv2');
    inv1_l = INVARIANT_SHORTHAND.get(inv1, inv1); inv2_l = INVARIANT_SHORTHAND.get(inv2, inv2);
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
        html.Tr([html.Td("Freq. at Mean"), html.Td(fmt_i('freq_at_mean_x')), html.Td(fmt_i('freq_at_mean_y'))]),
    ]
    comp_tbl = dbc.Table([html.Thead(html.Tr([html.Th("Statistic"), html.Th(inv1_l), html.Th(inv2_l)])), html.Tbody(body)], bordered=True, striped=True, hover=True, size="sm", className="mb-3")

    pair_body = html.Tbody([
        html.Tr([html.Td("# of Data Points"), html.Td(fmt_i('population'))]),
        html.Tr([html.Td("Peak Location"), html.Td(f"({get_stat('peak', 'x', 2)}, {get_stat('peak', 'y', 2)})")]),
        html.Tr([html.Td("Peak Frequency"), html.Td(fmt_i('peak_freq'))]),
    ])
    pair_tbl = dbc.Table(pair_body, bordered=True, striped=True, hover=True, size="sm")

    return dbc.Card([
        dbc.CardHeader(panel_state.get('title', 'Statistics')),
        dbc.CardBody([html.H5("Comparison", className="card-subtitle mb-2 text-muted"), comp_tbl, html.H5("Pairwise", className="card-subtitle mb-2 mt-3 text-muted"), pair_tbl], className="p-3")
    ], className="stat-card h-100 w-100", style={'overflowY': 'auto'})


def build_full_stats_table(panel_state, use_sci_notation=False):
    return create_combined_stats_table(panel_state, use_sci_notation)
