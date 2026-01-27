import dash_bootstrap_components as dbc
from dash import dcc, html
from constants import (
    INVARIANT_ORDER, INVARIANT_SHORTHAND, PLOTLY_COLORSCALES,
    MAX_GRAPHS
)

def build_config_panel():
    """Builds the main configuration panel"""

    return html.Div(
        className="left-panel",
        children=[
            html.Div(
                className="d-flex justify-content-between align-items-center",
                children=[
                    html.H3("ProtNRD v0.9", className="app-title mb-0"),
                    html.Div([
                         dcc.Clipboard(
                            target_id="share-url-box",
                            title="Copy Layout Link",
                            style={
                                "display": "inline-block",
                                "fontSize": 20,
                                "verticalAlign": "middle",
                                "color": "#007bff",
                                "cursor": "pointer"
                            },
                        ),
                        dbc.Tooltip("Copy Layout Link", target="share-url-box"),
                    ])
                ]
            ),
            # Hidden input to hold the generated URL for the clipboard
            dcc.Input(id="share-url-box", style={"display": "none"}),
            html.Hr(),
            html.H4("Configure Panel", id="active-panel-display"),

            # Triplet Input & Position Selector
            dbc.Row([
                dbc.Col([
                    dbc.Label("Triplet (e.g. AAA)", html_for='triplet-input'),
                    dbc.Input(
                        id='triplet-input', 
                        type='text', 
                        maxLength=3, 
                        value='AAA', 
                        style={'textTransform': 'uppercase'}
                    ),
                ], width=8),
                dbc.Col([
                    dbc.Label("Pos", html_for='position-dropdown'),
                    dcc.Dropdown(
                        id='position-dropdown', 
                        options=[
                            {'label': '1', 'value': 1}, 
                            {'label': '2', 'value': 2}, 
                            {'label': '3', 'value': 3}
                        ], 
                        value=1, 
                        clearable=False
                    )
                ], width=4)
            ], className="mb-2"),

            # Frequency & Rank Display
            html.Div(
                id='triplet-stats-container', 
                className="mb-4 text-muted small",
                style={'fontStyle': 'italic', 'paddingLeft': '2px'}
            ),

            dbc.Label("Component 1 (X-axis)", className="mt-1"),
            dcc.Dropdown(id='inv1-dropdown', options=[{'label': INVARIANT_SHORTHAND.get(i, i), 'value': i} for i in INVARIANT_ORDER], value='tau_NA'),
            dbc.Label("Component 2 (Y-axis)", className="mt-3"),
            dcc.Dropdown(id='inv2-dropdown', options=[{'label': INVARIANT_SHORTHAND.get(i, i), 'value': i} for i in INVARIANT_ORDER], value='tau_AC'),
            

            html.Hr(),

            html.Div(id='visual-options-container', children=[
                html.H5("Visual Options"),
                
                html.Div(id='scale-switch-container', children=[
                    dbc.Label("Scale"),
                    dbc.Switch(id='scale-switch', label="Linear / Log", value=True),
                ]),
                
                html.Div(id='colormap-container', children=[
                    dbc.Label("Colormap", className="mt-2"),
                    dcc.Dropdown(id='colormap-dropdown', options=[{'label': cs, 'value': cs} for cs in PLOTLY_COLORSCALES], value='Custom Rainbow'),
                ]),
                
                html.Div(id='xaxis-limit-container', children=[
                    dbc.Label("X-axis limits", id='xaxis-limit-label', className="mt-3"),
                    dbc.Row([dbc.Col(dbc.Input(id='xaxis-min-input', type='number', placeholder='Min')), dbc.Col(dbc.Input(id='xaxis-max-input', type='number', placeholder='Max')),]),
                ]),
                
                html.Div(id='yaxis-limit-container', children=[
                    dbc.Label("Y-axis limits", id='yaxis-limit-label', className="mt-2"),
                    dbc.Row([dbc.Col(dbc.Input(id='yaxis-min-input', type='number', placeholder='Min')), dbc.Col(dbc.Input(id='yaxis-max-input', type='number', placeholder='Max')),]),
                ]),
            ]),
            
            html.Div([
                dbc.Label("Stat Formatting"),
                dbc.Switch(id='sci-notation-switch', label="Fixed / Scientific", value=False),
            ], className="mt-3"),

            html.Div(
                id='query-warning-message', 
                style={'color': '#D9534F', 'fontSize': '0.8rem', 'marginTop': '10px', 'minHeight': '1.2rem'}
            ),
            dbc.Button("Load Data", id="generate-graph-button", color="primary", className="w-100 mt-4")
        ]
    )


def main_layout():
    """Main layout of the dashboard"""

    main_panel = html.Div(
        className="main-panel",
        children=[
            dcc.Store(id='panel-states-store', storage_type='session'),
            dcc.Store(id='active-panel-store', data=0, storage_type='session'),
            dcc.Store(id='last-clicked-panel-store'),
            dcc.Store(id='graph-job-store'),
            dcc.Store(id='status-message-store'),
            dcc.Store(id='sci-notation-store', storage_type='session', data=False),

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
        dbc.ModalHeader(
            id="focus-modal-header-title",
            close_button=True
        ),
        dbc.ModalBody(id="focus-modal-body", style={'height': '85vh'})
    ], id="focus-modal", fullscreen=True, scrollable=True)

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

    return html.Div(className="app-container-v8", children=[
        dcc.Location(id='url', refresh=False),
        build_config_panel(), main_panel, focus_modal, confirm_clear_modal,
        dcc.Download(id="download-html"), status_indicator,
        dcc.Interval(id='status-clear-interval', interval=4000, disabled=True)
    ])