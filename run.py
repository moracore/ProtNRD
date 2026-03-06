import os
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from dash import html
import dash_bootstrap_components as dbc

from v9.app import app as pairwise_app  # v9/ folder contains the Pairwise app
from v8.app import app as trimer_app    # v8/ folder contains the Trimer app

# Set PROTNRD_BASE to the sub-path the app is served under, with no trailing slash.
# Leave empty for local development.
#   Local:  PROTNRD_BASE=""        → served at /v8/ and /v9/
#   Server: PROTNRD_BASE=/protNRD  → served at /protNRD/v8/ and /protNRD/v9/
BASE = os.environ.get('PROTNRD_BASE', '')

# --- CRITICAL FIX: ISOLATE API ROUTING ---
# Dash apps under a middleware will send API requests to the root '/' by default.
# Dash locks 'requests_pathname_prefix' after initialization, so we bypass the
# read-only lock here to inject the paths dynamically without editing app.py.
for key in ['requests_pathname_prefix', 'routes_pathname_prefix']:
    pairwise_app.config._read_only.pop(key, None)
    trimer_app.config._read_only.pop(key, None)

pairwise_app.config.requests_pathname_prefix = f'{BASE}/v8/'
trimer_app.config.requests_pathname_prefix = f'{BASE}/v9/'

# Suppress strict callback validation errors during hot-reloads
pairwise_app.config.suppress_callback_exceptions = True
trimer_app.config.suppress_callback_exceptions = True

application = DispatcherMiddleware(
    pairwise_app.server,
    {
        f"{BASE}/v8": pairwise_app.server,
        f"{BASE}/v9": trimer_app.server,
    },
)

if __name__ == "__main__":
    print("-------------------------------------------------------")
    print(" ProtNRD Running on http://localhost:8050/ ")
    print("-------------------------------------------------------")
    run_simple(
        "localhost",
        8050,
        application,
        use_reloader=True,
        use_debugger=True,
    )