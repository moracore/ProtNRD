import json
import numpy as np
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State, no_update
import dash_bootstrap_components as dbc
from constants import INVARIANT_SHORTHAND, N_RAINBOW, MAX_GRAPHS

def safe_float(val):
    """Safely converts a value to float, returning 0.0 on failure."""
    if val is None: return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def format_val(val, is_angle=True, use_sci=False):
    """Formatting helper that handles both strings and numbers."""
    if val is None or val == "N/A": return "N/A"
    
    try:
        f_val = float(val)
    except (ValueError, TypeError):
        return str(val)

    if use_sci: 
        return f"{f_val:.1e}"
    
    if is_angle: 
        return f"{f_val:.1f}"
    
    if abs(f_val) < 1e-3 and abs(f_val) > 0: 
        return f"{f_val:.3e}"
    
    return f"{f_val:.3f}"

def build_overlay(stats):
    """Quick Stats Overlay with safe casting."""
    if not stats: return None
    
    pop = safe_float(stats.get('frequency', 0))
    peak_phi = safe_float(stats.get('phi_psi_peak_phi', 0))
    peak_psi = safe_float(stats.get('phi_psi_peak_psi', 0))
    peak_f = safe_float(stats.get('phi_psi_peak_f', 0))
    
    return html.Div([
        html.Div([html.Span("N: ", className="fw-bold"), f"{int(pop):,}"]),
        html.Div([html.Span("Peak: ", className="fw-bold"), f"({peak_phi:.0f}°, {peak_psi:.0f}°)"]),
        html.Div([html.Span("Max Freq: ", className="fw-bold"), f"{int(peak_f):,}"]),
    ], className="stats-overlay", style={
        'position': 'absolute', 'bottom': '10px', 'left': '10px', 
        'backgroundColor': 'rgba(255,255,255,0.85)', 'padding': '5px 8px', 
        'borderRadius': '4px', 'fontSize': '0.75rem', 'pointerEvents': 'none',
        'border': '1px solid #ccc', 'boxShadow': '0 2px 4px rgba(0,0,0,0.1)'
    })

def create_3D_figure(data, title, uirevision_key, log_scale, colormap, x_lims, y_lims):
    if not data or 'points' not in data:
        fig = go.Figure()
        fig.update_layout(title="No 3D Data", margin=dict(l=0, r=0, b=0, t=40))
        return fig

    pts = data.get('points', [])
    if not pts: return go.Figure()
    
    xs, ys, zs = zip(*pts)
    x_centers, y_centers = np.unique(xs), np.unique(ys)
    
    # Initialize grid with zeros
    z_grid = np.zeros((len(y_centers), len(x_centers)))
    
    x_map = {v: i for i, v in enumerate(x_centers)}
    y_map = {v: i for i, v in enumerate(y_centers)}
    
    for x, y, z in pts:
        z_grid[y_map[y], x_map[x]] = float(z)

    # 1. Apply Log Scale if requested
    # We do this BEFORE setting NaNs, because log10(0 + 1) = 0, keeping the 'floor' at 0 for now.
    if log_scale:
        z_data = np.log10(z_grid + 1)
    else:
        z_data = z_grid

    # 2. Apply Transparency
    # Any value that is exactly 0 (meaning 0 freq) becomes NaN.
    # Plotly does not render NaN values, creating true transparency.
    z_data[z_data == 0] = np.nan

    # 3. Create Surface
    # We pass z_data to both 'z' (height) and 'surfacecolor' (color)
    fig = go.Figure(data=[go.Surface(
        x=x_centers, y=y_centers, 
        z=z_data,             # Height determines the shape
        surfacecolor=z_data,  # Color matches the height (Log or Linear)
        colorscale=N_RAINBOW if colormap == "Custom Rainbow" else colormap,
        showscale=False,
        connectgaps=False     # CRITICAL: Do not interpolate over the NaNs
    )])

    # Determine Z-axis title
    z_title = "Log(Freq)" if log_scale else "Freq"

    fig.update_layout(
        title=dict(text=title, font=dict(size=14)),
        uirevision=uirevision_key,
        scene=dict(
            xaxis=dict(title="φ", range=x_lims),
            yaxis=dict(title="ψ", range=y_lims),
            zaxis=dict(title=z_title),
            camera=dict(eye=dict(x=-1.4, y=-1.4, z=1.4))
        ),
        margin=dict(l=10, r=10, b=10, t=30)
    )
    return fig

def build_stat_section(title, headers, rows):
    return html.Div([
        html.H6(title, className="mt-2 mb-1 text-primary border-bottom pb-1", style={'fontSize': '0.8rem'}),
        dbc.Table([
            html.Thead(html.Tr([html.Th(h) for h in headers])),
            html.Tbody([html.Tr([html.Td(c) for c in r]) for r in rows])
        ], bordered=True, hover=True, size="sm", className="mb-0", style={'fontSize': '0.7rem'})
    ])

def build_comprehensive_stats(stats, use_sci):
    """Maps the 77 metrics into a structured UI layout."""
    if not stats: return html.Div("No stats available.")

    # 1. Global 2D Profile
    g2d_rows = [
        ["Joint Mean", f"({format_val(stats.get('phi_psi_mean_phi'))}°, {format_val(stats.get('phi_psi_mean_psi'))}°)", "Corr (ρcc)", format_val(stats.get('phi_psi_corr'))],
        ["Joint Mode", f"({format_val(stats.get('phi_psi_peak_phi'))}°, {format_val(stats.get('phi_psi_peak_psi'))}°)", "Rigidity (R2D)", format_val(stats.get('phi_psi_R2D'))],
        ["Freq @ Mean", f"{int(safe_float(stats.get('phi_psi_mean_f'))):,}", "Freq @ Mode", f"{int(safe_float(stats.get('phi_psi_peak_f'))):,}"]
    ]
    
    # 2. Torsions (phi, psi, omega)
    torsion_rows = []
    for p in ['phi', 'psi', 'omg']:
        torsion_rows.append([
            INVARIANT_SHORTHAND.get(p if p != 'omg' else 'tau_CN', p),
            format_val(stats.get(f'{p}_mean')),
            format_val(stats.get(f'{p}_R')),
            format_val(stats.get(f'{p}_peak')),
            f"{int(safe_float(stats.get(f'{p}_f_win'))):,}"
        ])

    # 3. Bond Geometries (Lengths & Angles)
    geom_rows = []
    # Lengths
    for l in ['len_N', 'len_A', 'len_C']:
        geom_rows.append([
            INVARIANT_SHORTHAND.get(l.replace('len', 'length').replace('_', ''), l),
            format_val(stats.get(f'{l}_mean'), is_angle=False, use_sci=use_sci),
            format_val(stats.get(f'{l}_std'), is_angle=False, use_sci=use_sci),
            f"{int(safe_float(stats.get(f'{l}_f_win'))):,}"
        ])
    # Angles
    for a in ['ang_N', 'ang_A', 'ang_C']:
        geom_rows.append([
            INVARIANT_SHORTHAND.get(a.replace('ang', 'angle').replace('_', ''), a),
            format_val(stats.get(f'{a}_mean')),
            format_val(stats.get(f'{a}_std')),
            f"{int(safe_float(stats.get(f'{a}_f_win'))):,}"
        ])

    return html.Div([
        html.Div([
            html.Span("Total Frequency: ", className="text-muted"),
            html.B(f"{int(safe_float(stats.get('frequency'))):,}")
        ], className="mb-2 text-end"),
        
        build_stat_section("Global 2D Profile", ["Metric", "Value", "Metric", "Value"], g2d_rows),
        build_stat_section("Backbone Torsions", ["Invariant", "Mean", "Rigid (R)", "Peak", "F_Win"], torsion_rows),
        build_stat_section("Bond Geometry", ["Invariant", "Mean", "Std Dev", "F_Win"], geom_rows)
    ], className="p-2")

def register_rendering_callbacks(app):
    @app.callback(
        [Output({'type': 'graph-col', 'index': i}, 'children') for i in range(MAX_GRAPHS)],
        Input('panel-states-store', 'data'),
        Input('active-panel-store', 'data'),
        Input('sci-notation-store', 'data')
    )
    def update_all_panels(panel_states_json, active_panel_index, sci_notation):
        panel_states = json.loads(panel_states_json or '{}')
        outputs = []

        for i in range(MAX_GRAPHS):
            state = panel_states.get(str(i))
            is_active = (i == active_panel_index)
            
            # Button overlay logic
            buttons = html.Div([
                dbc.Button(html.I(className="bi bi-box-arrow-up-right"), id={'type': 'focus-button', 'index': i}, size="sm", className="me-1", title="Focus View"),
                dbc.Button(html.I(className="bi bi-download"), id={'type': 'download-button', 'index': i}, size="sm", className="me-1", title="Download Stats"),
                dbc.Button(html.I(className="bi bi-gear-fill"), id={'type': 'config-button', 'index': i}, size="sm", color="primary" if is_active else "secondary")
            ], style={'position': 'absolute', 'top': '5px', 'right': '5px', 'zIndex': 10})

            if not state:
                outputs.append(html.Div([
                    html.I(className="bi bi-plus-lg", style={'fontSize': '2rem', 'color': '#ccc'}),
                    buttons
                ], className=f"placeholder-panel d-flex justify-content-center align-items-center {'active' if is_active else ''}", id={'type': 'placeholder-button', 'index': i}, style={'position': 'relative'}))
                continue

            # Content Logic
            view = state.get('view', 'graph')
            overlay = None

            if view == 'graph':
                fig = create_3D_figure(
                    state.get('figure_data'), state.get('title'), state.get('uirevision_key'),
                    state.get('log_scale'), state.get('colormap'), state.get('x_lims'), state.get('y_lims')
                )
                content = dcc.Graph(figure=fig, style={'height': '100%'}, config={'displayModeBar': False})
                overlay = build_overlay(state.get('full_stats'))
            else:
                content = build_comprehensive_stats(state.get('full_stats'), sci_notation)

            # Wrapper with View Toggle
            view_toggle = dbc.Button(
                html.I(className="bi bi-table" if view == 'graph' else "bi bi-box"),
                id={'type': 'toggle-view-button', 'index': i},
                size="sm", style={'position': 'absolute', 'bottom': '5px', 'right': '5px', 'zIndex': 10}
            )

            elements = [buttons, view_toggle, content]
            if overlay: elements.append(overlay)

            outputs.append(html.Div(elements, className="graph-item p-1", style={'position': 'relative', 'height': '100%'}))

        return outputs