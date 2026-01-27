from dash import Dash
import dash_bootstrap_components as dbc
import layouts
from callbacks import register_callbacks

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

app.layout = layouts.main_layout()
register_callbacks(app)

if __name__ == '__main__':
    app.run(debug=False, port=8050)