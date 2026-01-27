from dash import Dash
import dash_bootstrap_components as dbc
import layouts
from callbacks import register_callbacks # Import from the new package

# Initialize the app for v6, loading Bootstrap themes and icons
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    # suppress_callback_exceptions=True # Might be needed if callbacks target dynamic content
    # prevent_initial_callbacks=True # Often useful to prevent callbacks firing on load
)
server = app.server

# Set the app layout and register callbacks
app.layout = layouts.main_layout()
register_callbacks(app) # Call the main registration function

# Run the app
if __name__ == '__main__':
    # Set debug=False for production/deployment
    app.run(debug=True, port=8050)
