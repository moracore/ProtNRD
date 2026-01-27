import dash_bootstrap_components as dbc
from dash import dcc, html
from constants import INVARIANT_ORDER, INVARIANT_SHORTHAND, PLOTLY_COLORSCALES, MAX_GRAPHS

def build_config_panel():
    """Builds the main configuration panel."""
    return html.Div(
        className="left-panel",
        children=[
            html.H3("K-mer Dashboard", className="app-title"),
            html.Hr(),
            html.H4("Configure Panel", id="active-panel-display"),
            
            dbc.Label("Invariant 1 (X-axis)"),
            dcc.Dropdown(id='inv1-dropdown', options=[{'label': f"{INVARIANT_SHORTHAND.get(i, i)} ({i})", 'value': i} for i in INVARIANT_ORDER], value='tau_NA'),
            
            dbc.Label("Invariant 2 (Y-axis)", className="mt-3"),
            dcc.Dropdown(id='inv2-dropdown', options=[{'label': f"{INVARIANT_SHORTHAND.get(i, i)} ({i})", 'value': i} for i in INVARIANT_ORDER], value='tau_AC'),
            
            dbc.Label("Residue Offset", className="mt-3"),
            dcc.Dropdown(id='offset-dropdown', options=[{'label': f'+{i}', 'value': i} for i in range(5)], value=0),
            
            html.Hr(),
            html.H5("Visual Options"),
            dbc.Label("Scale"),
            dbc.Switch(id='scale-switch', label="Log / Linear", value=True),
            dbc.Label("Colormap", className="mt-2"),
            dcc.Dropdown(id='colormap-dropdown', options=[{'label': cs, 'value': cs} for cs in PLOTLY_COLORSCALES], value='Custom Rainbow'),

            # --- UPDATED: Added IDs to labels ---
            dbc.Label("X-axis limits", id='xaxis-limit-label', className="mt-3"),
            dbc.Row([
                dbc.Col(dbc.Input(id='xaxis-min-input', type='number', placeholder='Min')),
                dbc.Col(dbc.Input(id='xaxis-max-input', type='number', placeholder='Max')),
            ]),

            dbc.Label("Y-axis limits", id='yaxis-limit-label', className="mt-2"),
            dbc.Row([
                dbc.Col(dbc.Input(id='yaxis-min-input', type='number', placeholder='Min')),
                dbc.Col(dbc.Input(id='yaxis-max-input', type='number', placeholder='Max')),
            ]),
            # --- END UPDATE ---

            dbc.Button("Generate Graph", id="generate-graph-button", color="primary", className="w-100 mt-4")
        ]
    )

def main_layout():
    """Defines the main layout of the dashboard."""
    main_panel = html.Div(
        className="main-panel",
        children=[
            dcc.Store(id='panel-states-store', storage_type='session'),
            dcc.Store(id='active-panel-store', data=0, storage_type='session'),
            dcc.Store(id='last-clicked-panel-store'),
            dcc.Store(id='graph-job-store'),
            dcc.Store(id='status-message-store'),
            
            dbc.Row(
                [
                    dbc.Col(
                        id={'type': 'graph-col', 'index': i},
                        children=[],
                        width=12, md=6, lg=4,
                        className="h-50 p-2"
                    ) for i in range(MAX_GRAPHS)
                ],
                id='graph-grid-container',
                className="g-0 flex-grow-1"
            )
        ]
    )

    focus_modal = dbc.Modal([
        dbc.ModalHeader(id="focus-modal-header"),
        dbc.ModalBody(dcc.Graph(id='focus-graph', style={'height': '80vh'}))
    ], id="focus-modal", fullscreen=True)

    confirm_clear_modal = dbc.Modal([
        dbc.ModalHeader(dbc.ModalTitle("Confirm Clear")),
        dbc.ModalBody("Are you sure you want to clear this graph panel?"),
        dbc.ModalFooter([
            dbc.Button("Cancel", id="cancel-clear-button", color="secondary"),
            dbc.Button("Clear", id="confirm-clear-button", color="danger"),
        ])
    ], id="confirm-clear-modal", is_open=False, centered=True)

    status_indicator = html.Div(id='status-indicator', style={
        'position': 'fixed', 'bottom': '20px', 'left': '20px',
        'backgroundColor': 'rgba(0, 0, 0, 0.8)', 'color': 'white',
        'padding': '10px 15px', 'borderRadius': '5px', 'zIndex': 1050,
        'transition': 'opacity 0.3s ease-in-out', 'opacity': 0,
        'fontSize': '14px', 'fontFamily': 'sans-serif'
    })

    return html.Div(className="app-container-v5", children=[
        build_config_panel(), main_panel, focus_modal, confirm_clear_modal,
        dcc.Download(id="download-html"), status_indicator,
        dcc.Interval(id='status-clear-interval', interval=4000, disabled=True)
    ])

