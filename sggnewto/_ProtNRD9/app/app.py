from dash import Dash
import dash_bootstrap_components as dbc
import layouts
from callbacks import register_callbacks

# ProtNRD v0.9 Entry Point
app = Dash(
    __name__,
    external_stylesheets=[
        dbc.themes.BOOTSTRAP, 
        dbc.icons.BOOTSTRAP,
        'assets/style.css'
    ],
    suppress_callback_exceptions=True
)
server = app.server

# Initialize the v0.9 Multi-Panel Layout
app.layout = layouts.main_layout()

# Register the distributed callback system (Fetching, Rendering, Interactions)
register_callbacks(app)

if __name__ == '__main__':
    # Default port updated to your preferred development port
    app.run(debug=False, port=8055)