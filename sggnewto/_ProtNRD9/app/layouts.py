import dash_bootstrap_components as dbc
from dash import dcc, html
from constants import (
    INVARIANT_SHORTHAND, DROPDOWN_ORDER, PLOTLY_COLORSCALES,
    MAX_GRAPHS, AMINO_ACIDS
)

def build_config_panel():
    res_options = [{'label': r, 'value': r} for r in AMINO_ACIDS]
    
    return html.Div(
        className="left-panel",
        children=[
            html.H3("ProtNRD v0.9", className="app-title"),
            html.Hr(),
            
            # --- 1. Triplet Construction ---
            dbc.Label("Construct 3-mer Sequence", className="fw-bold mt-1"),
            dbc.Row([
                dbc.Col([dbc.Label("Pos 1", className="small text-muted"), dcc.Dropdown(id='res1-dropdown', options=res_options, value='A', clearable=False)], width=4),
                dbc.Col([dbc.Label("Pos 2", className="small text-muted"), dcc.Dropdown(id='res2-dropdown', options=res_options, value='A', clearable=False)], width=4),
                dbc.Col([dbc.Label("Pos 3", className="small text-muted"), dcc.Dropdown(id='res3-dropdown', options=res_options, value='A', clearable=False)], width=4),
            ], className="g-1 mb-2"),

            dbc.Label("Focus Position", className="small text-muted mt-1"),
            dbc.ButtonGroup([
                dbc.Button("1", id="focus-btn-1", color="primary", outline=False, size="sm"),
                dbc.Button("2", id="focus-btn-2", color="primary", outline=True, size="sm"),
                dbc.Button("3", id="focus-btn-3", color="primary", outline=True, size="sm"),
            ], className="w-100 mb-3"),
            dcc.Store(id='focus-position-store', data=1),

            # --- 2. Components (Side-by-Side) ---
            dbc.Label("Torsion Analysis", className="fw-bold mt-3"),
            dbc.Row([
                dbc.Col([
                    dbc.Label("X-Axis", className="small"),
                    dcc.Dropdown(id='inv1-dropdown', options=[{'label': INVARIANT_SHORTHAND.get(i, i), 'value': i} for i in DROPDOWN_ORDER], value='tau_NA', clearable=False)
                ], width=6),
                dbc.Col([
                    dbc.Label("Y-Axis", className="small"),
                    dcc.Dropdown(id='inv2-dropdown', options=[{'label': INVARIANT_SHORTHAND.get(i, i), 'value': i} for i in DROPDOWN_ORDER], value='tau_AC', clearable=False)
                ], width=6),
            ], className="g-1 mb-2"),

            # --- 3. Axis Limits (Always Visible) ---
            dbc.Label("Axis Limits", className="fw-bold mt-3"),
            dbc.Row([
                dbc.Col(dbc.Label("X Min", className="small text-muted"), width=3),
                dbc.Col(dbc.Input(id='xaxis-min-input', type='number', value=-180, size="sm"), width=3),
                dbc.Col(dbc.Label("X Max", className="small text-muted"), width=3),
                dbc.Col(dbc.Input(id='xaxis-max-input', type='number', value=180, size="sm"), width=3),
            ], className="g-1 mb-1 align-items-center"),
            
            dbc.Row([
                dbc.Col(dbc.Label("Y Min", className="small text-muted"), width=3),
                dbc.Col(dbc.Input(id='yaxis-min-input', type='number', value=-180, size="sm"), width=3),
                dbc.Col(dbc.Label("Y Max", className="small text-muted"), width=3),
                dbc.Col(dbc.Input(id='yaxis-max-input', type='number', value=180, size="sm"), width=3),
            ], className="g-1 align-items-center"),

            # --- 4. Visuals ---
            dbc.Label("Visual Options", className="fw-bold mt-4"),
            html.Div([
                # Hidden switch, defaulted to True to enforce "always log" preference visually
                dbc.Switch(id='scale-switch', label="Log Color Scale", value=True, className="mb-2"),
                dbc.Label("Colormap", className="small"),
                dcc.Dropdown(id='colormap-dropdown', options=[{'label': cs, 'value': cs} for cs in PLOTLY_COLORSCALES], value='Custom Rainbow', clearable=False),
                dbc.Switch(id='sci-notation-switch', label="Scientific Notation", value=False, className="mt-3"),
            ]),

            html.Div(id='query-warning-message', style={'color': '#D9534F', 'fontSize': '0.8rem', 'marginTop': '10px'}),
            dbc.Button("Load Data", id="generate-graph-button", color="primary", className="w-100 mt-4 shadow-sm")
        ]
    )

def main_layout():
    return html.Div(className="app-container-v8", children=[
        build_config_panel(),
        html.Div(className="main-panel", children=[
            dcc.Store(id='panel-states-store', storage_type='session'),
            dcc.Store(id='active-panel-store', data=0, storage_type='session'),
            dcc.Store(id='last-clicked-panel-store'),
            dcc.Store(id='status-message-store'),
            dcc.Store(id='sci-notation-store', storage_type='session', data=False),
            dbc.Row([
                dbc.Col(id={'type': 'graph-col', 'index': i}, width=12, md=6, lg=4, className="h-50 p-2") 
                for i in range(MAX_GRAPHS)
            ], id='graph-grid-container', className="g-0 flex-grow-1")
        ]),
        dbc.Modal([
            dbc.ModalHeader(id="focus-modal-header-title", close_button=True),
            dbc.ModalBody(id="focus-modal-body", style={'height': '85vh'})
        ], id="focus-modal", fullscreen=True),
        dbc.Modal([
            dbc.ModalHeader("Confirm Clear"),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="cancel-clear-button", color="secondary"),
                dbc.Button("Clear", id="confirm-clear-button", color="danger")
            ])
        ], id="confirm-clear-modal", is_open=False),
        dcc.Download(id="download-html"),
        html.Div(id='status-indicator', style={'position': 'fixed', 'bottom': '20px', 'left': '20px', 'backgroundColor': 'rgba(0,0,0,0.8)', 'color': 'white', 'padding': '10px', 'borderRadius': '5px', 'opacity': 0}),
        dcc.Interval(id='status-clear-interval', interval=4000, disabled=True)
    ])