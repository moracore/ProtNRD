from dash import Dash
from .interactions import register_interaction_callbacks

def register_callbacks(app: Dash):
    """Registers all callbacks for the application."""
    register_interaction_callbacks(app)