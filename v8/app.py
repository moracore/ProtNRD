from dash import Dash
import dash_bootstrap_components as dbc
from . import layouts
from .callbacks import register_callbacks

app = Dash(
    __name__,
    title='ProtNRD | Trimer',
    requests_pathname_prefix='/v9/',
    external_stylesheets=[
        dbc.themes.BOOTSTRAP, 
        dbc.icons.BOOTSTRAP,
        'assets/style.css'
    ],
    suppress_callback_exceptions=True
)
server = app.server

app.layout = layouts.main_layout()
register_callbacks(app)

if __name__ == '__main__':
    app.run(debug=False, port=8056)