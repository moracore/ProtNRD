import dash_bootstrap_components as dbc
from dash import dcc, html
from pathlib import Path
from .constants import (
    INVARIANT_ORDER, INVARIANT_SHORTHAND, PLOTLY_COLORSCALES,
    MAX_GRAPHS, BASE_PATH
)

_HERE = Path(__file__).parent


def _read_readme(path):
    try:
        return path.read_text()
    except Exception:
        return "_Content not available._"


_PAIRWISE_README = _read_readme(_HERE / "README.md")
_TRIMER_README = _read_readme(_HERE.parent / "v9" / "README.md")

_REFERENCE_CONTENT = """\
## Geometric Invariants

Nine backbone properties are available as plot axes, computed from the N, Cα, and C atomic positions of each residue.

**Torsion angles** (−180° to 180°)

- **phi (φ)** — N → Cα torsion angle.
- **psi (ψ)** — Cα → C torsion angle.
- **omega (ω)** — C → N torsion angle; measures peptide bond planarity.

**Bond angles** (radians)

- **Angle N** — N–Cα–C
- **Angle A** — Cα–C–N
- **Angle C** — C–N–Cα

**Bond lengths** (Å)

- **Length NA** — N to Cα
- **Length AC** — Cα to C
- **Length CN** — C to next N
"""


def build_config_panel():
    """Builds the main configuration panel"""

    return html.Div(
        id="config-left-panel",
        className="left-panel",
        children=[
            html.Div(
                className="d-flex justify-content-between align-items-center",
                children=[
                    html.Div(className="d-flex align-items-center gap-2", children=[
                        html.H3("ProtNRD", className="app-title mb-0"),
                        dbc.ButtonGroup([
                            dbc.Button("Pairwise", href=f"{BASE_PATH}/v8/", external_link=True, size="sm", outline=True, color="secondary", className="mode-btn"),
                            dbc.Button("Trimer", href=f"{BASE_PATH}/v9/", external_link=True, size="sm", color="primary", className="mode-btn"),
                        ], size="sm", className="mode-toggle"),
                    ]),
                    html.Div([
                        # Mobile close button (managed via CSS visibility)
                        dbc.Button(
                            html.I(className="bi bi-x-lg"),
                            id="mobile-menu-close",
                            color="link",
                            className="mobile-close-btn p-0 text-dark me-3",
                            style={"display": "none", "fontSize": "1.2rem"}
                        ),
                    ])
                ]
            ),
            html.A(
                [html.I(className="bi bi-question-circle me-1"), "How to use ProtNRD"],
                id="help-btn-sidebar",
                href="#",
                className="sidebar-help-link",
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

    # Define the mobile header (hidden on desktop)
    mobile_header = html.Div(
        id="mobile-header",
        className="mobile-header",
        style={"display": "none"},
        children=[
            html.Div(className="d-flex align-items-center gap-2", children=[
                html.H3("ProtNRD", className="app-title mb-0", style={"fontSize": "1.2rem"}),
                dbc.ButtonGroup([
                    dbc.Button("Pairwise", href=f"{BASE_PATH}/v8/", external_link=True, size="sm", outline=True, color="secondary", className="mode-btn"),
                    dbc.Button("Trimer", href=f"{BASE_PATH}/v9/", external_link=True, size="sm", color="primary", className="mode-btn"),
                ], size="sm", className="mode-toggle"),
                html.A(
                    html.I(className="bi bi-question-circle"),
                    id="help-btn-mobile",
                    href="#",
                    className="mobile-help-btn",
                    title="How to use ProtNRD",
                ),
            ]),
            dbc.Button(html.I(className="bi bi-list"), id="mobile-menu-toggle", color="primary", size="sm")
        ]
    )

    # Define the new footer
    app_footer = html.Div(
        className="app-footer",
        children=[
            html.Div(
                className="footer-left",
                children=[
                    html.A(
                        [html.I(className="bi bi-question-circle me-1"), "How to use ProtNRD"],
                        id="help-btn-footer",
                        href="#",
                        className="footer-edu-link",
                        style={"textDecoration": "underline", "cursor": "pointer"}
                    ),
                    html.A(
                        [html.I(className="bi bi-link-45deg me-1"), "Share Layout"],
                        id="share-layout-link",
                        href="#",
                        style={"textDecoration": "underline", "color": "#E8603C", "cursor": "pointer"}
                    ),
                    dcc.Clipboard(
                        target_id="share-url-box",
                        style={"display": "none"},
                    ),
                ]
            ),
            html.Div(
                className="footer-right",
                children=[
                    html.A("Gabriel Newton", href="https://github.com/moracore", target="_blank", style={"textDecoration": "underline"}),
                    html.Span(" | ", className="footer-separator"),
                    html.A("The University of Liverpool", href="https://www.liverpool.ac.uk/", target="_blank", style={"textDecoration": "underline"}),
                    html.Div(className="footer-logo")
                ]
            )
        ]
    )

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
                        className="custom-graph-col p-2"
                    ) for i in range(MAX_GRAPHS)
                ],
                id='graph-grid-container',
                className="g-0 flex-grow-1"
            ),
            app_footer
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

    help_modal = dbc.Modal([
        dbc.ModalHeader(
            dbc.ModalTitle("How to use ProtNRD"),
            className="modal-header-accent",
            close_button=True
        ),
        dbc.ModalBody(
            dbc.Tabs([
                dbc.Tab(
                    dcc.Markdown(_TRIMER_README),
                    label="Trimer Mode",
                    tab_id="tab-trimer",
                    className="pt-3",
                ),
                dbc.Tab(
                    dcc.Markdown(_PAIRWISE_README),
                    label="Pairwise Mode",
                    tab_id="tab-pairwise",
                    className="pt-3",
                ),
                dbc.Tab(
                    [
                        dcc.Markdown(_REFERENCE_CONTENT, className="pt-3"),
                        html.Hr(),
                        html.H6("Educational Resources", className="text-muted mb-2"),
                        html.Div(className="d-flex gap-3 flex-wrap", children=[
                            html.A("Protein Structure", href="https://en.wikipedia.org/wiki/Protein_structure", target="_blank", style={"textDecoration": "underline"}),
                            html.A("Ramachandran Plot", href="https://en.wikipedia.org/wiki/Ramachandran_plot", target="_blank", style={"textDecoration": "underline"}),
                            html.A("ProtNRD GitHub", href="https://github.com/moracore/ProtNRD/releases/latest", target="_blank", style={"textDecoration": "underline"}),
                        ]),
                    ],
                    label="Reference",
                    tab_id="tab-ref",
                ),
            ], active_tab="tab-trimer")
        )
    ], id="help-modal", fullscreen=True, scrollable=True, is_open=False)

    status_indicator = html.Div(id='status-indicator', style={
        'position': 'fixed', 'bottom': '20px', 'left': '20px',
        'backgroundColor': 'rgba(0, 0, 0, 0.8)', 'color': 'white',
        'padding': '10px 15px', 'borderRadius': '5px', 'zIndex': 1050,
        'transition': 'opacity 0.3s ease-in-out', 'opacity': 0,
        'fontSize': '14px', 'fontFamily': 'sans-serif'
    })

    return html.Div(className="app-container-v8", children=[
        dcc.Location(id='url', refresh=False),
        mobile_header,
        build_config_panel(),
        main_panel,
        focus_modal,
        confirm_clear_modal,
        help_modal,
        dcc.Download(id="download-html"),
        status_indicator,
        dcc.Interval(id='status-clear-interval', interval=4000, disabled=True)
    ])