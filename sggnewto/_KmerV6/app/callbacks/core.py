from dash import Dash
from .data_fetching import register_data_fetching_callbacks
from .rendering import register_rendering_callbacks
from .interactions import register_interaction_callbacks

def register_callbacks(app: Dash):
    """Registers all callbacks for the application."""
    register_data_fetching_callbacks(app)
    register_rendering_callbacks(app)
    register_interaction_callbacks(app)
