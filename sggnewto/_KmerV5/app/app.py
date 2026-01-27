from dash import Dash
import dash_bootstrap_components as dbc
import layouts
import callbacks

# Initialize the app for v5, loading Bootstrap themes and icons
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    # suppress_callback_exceptions is not needed with the new static layout
)
server = app.server

# Set the app layout and register callbacks
app.layout = layouts.main_layout()
callbacks.register_callbacks(app)

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=8050)

