import dash_bootstrap_components as dbc
from dash import dcc, html
from constants import (
    INVARIANT_ORDER, INVARIANT_SHORTHAND, PLOTLY_COLORSCALES,
    MAX_GRAPHS, RESIDUE_CONTEXTS, AMINO_ACID_NAMES
)

def build_config_panel():
    """Builds the main configuration panel."""

    residue_options = [
        {'label': AMINO_ACID_NAMES.get(res, res), 'value': res} 
        for res in RESIDUE_CONTEXTS
    ]
    default_residue = "A"

    return html.Div(
        className="left-panel",
        children=[
            html.H3("ProtNRD v0.8.3", className="app-title"),
            html.Hr(),
            html.H4("Configure Panel", id="active-panel-display"),

            dbc.Label("Residue Step"),
            dcc.Dropdown(id='offset-dropdown', options=[{'label': f'+{i}', 'value': i} for i in range(5)], value=0),

            dbc.Label("Component 1 (X-axis)", className="mt-3"),
            dcc.Dropdown(id='inv1-dropdown', options=[{'label': INVARIANT_SHORTHAND.get(i, i), 'value': i} for i in INVARIANT_ORDER], value='tau_NA'),
            dbc.Label("Component 2 (Y-axis)", className="mt-3"),
            dcc.Dropdown(id='inv2-dropdown', options=[{'label': INVARIANT_SHORTHAND.get(i, i), 'value': i} for i in INVARIANT_ORDER], value='tau_AC'),
            
            html.Div(id='res1-container', className='res-container mt-3', children=[
                html.Div(className='label-checkbox-row', children=[
                    dbc.Label("Residue 1 Type. Focus:", html_for='pos-0-checkbox', className="dbc-label"),
                    dbc.Checkbox(id='pos-0-checkbox', value=True, className='pos-checkbox-inline')
                ]),
                dcc.Dropdown(id='res1-dropdown', options=residue_options, value=default_residue)
            ]),

            html.Div(id='res2-container', className='res-container mt-3', children=[
                html.Div(className='label-checkbox-row', children=[
                    dbc.Label("Residue 2 Type. Focus:", html_for='pos-1-checkbox', className="dbc-label"),
                    dbc.Checkbox(id='pos-1-checkbox', value=False, className='pos-checkbox-inline')
                ]),
                dcc.Dropdown(id='res2-dropdown', options=residue_options, value=default_residue)
            ]),

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
    """Defines the main layout of the dashboard."""

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
        build_config_panel(), main_panel, focus_modal, confirm_clear_modal,
        dcc.Download(id="download-html"), status_indicator,
        dcc.Interval(id='status-clear-interval', interval=4000, disabled=True)
    ])