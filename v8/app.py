from dash import Dash
import dash_bootstrap_components as dbc
from . import layouts
from .callbacks import register_callbacks

app = Dash(
    __name__,
    title="ProtNRD | Pairwise",
    requests_pathname_prefix='/v8/',
    external_stylesheets=[
        dbc.themes.BOOTSTRAP, 
        dbc.icons.BOOTSTRAP,
        '/assets/style.css'
    ],
    suppress_callback_exceptions=True
)
server = app.server

app.layout = layouts.main_layout()
register_callbacks(app)

# Note: The if __name__ block is fine, it only runs if you run v8/app.py directly
if __name__ == '__main__':
    app.run(debug=False, port=8056)