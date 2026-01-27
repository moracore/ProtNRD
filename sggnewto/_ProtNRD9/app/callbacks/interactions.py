import json
import csv
import io
import plotly.io as pio
from dash import dcc, html, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
from .rendering import create_3D_figure, build_comprehensive_stats
import time

def register_interaction_callbacks(app):

    # --- 1. Focus Position Buttons (Radio Logic) ---
    @app.callback(
        Output("focus-btn-1", "outline"),
        Output("focus-btn-2", "outline"),
        Output("focus-btn-3", "outline"),
        Output("focus-position-store", "data"),
        Input("focus-btn-1", "n_clicks"),
        Input("focus-btn-2", "n_clicks"),
        Input("focus-btn-3", "n_clicks"),
        prevent_initial_call=True
    )
    def update_focus_buttons(btn1, btn2, btn3):
        """
        Updates the style of the 1/2/3 buttons to act like radio buttons.
        Solid (outline=False) = Selected.
        """
        triggered_id = ctx.triggered_id
        if not triggered_id: return no_update

        # Default: All outline (inactive)
        s1, s2, s3 = True, True, True
        focus_val = 1

        if triggered_id == "focus-btn-1":
            s1, focus_val = False, 1
        elif triggered_id == "focus-btn-2":
            s2, focus_val = False, 2
        elif triggered_id == "focus-btn-3":
            s3, focus_val = False, 3
            
        return s1, s2, s3, focus_val

    # --- 2. Sidebar Synchronization (Update Inputs when Panel Clicked) ---
    @app.callback(
        Output('active-panel-store', 'data'), 
        Output('active-panel-display', 'children'),
        # Residues
        Output('res1-dropdown', 'value'), 
        Output('res2-dropdown', 'value'), 
        Output('res3-dropdown', 'value'),
        # Axes
        Output('inv1-dropdown', 'value'), 
        Output('inv2-dropdown', 'value'),
        # Visuals
        Output('scale-switch', 'value'),
        Output('colormap-dropdown', 'value'),
        Output('sci-notation-switch', 'value'),
        # Sync Focus Buttons to the Panel's state
        Output("focus-btn-1", "outline", allow_duplicate=True),
        Output("focus-btn-2", "outline", allow_duplicate=True),
        Output("focus-btn-3", "outline", allow_duplicate=True),
        Output("focus-position-store", "data", allow_duplicate=True),
        
        Input({'type': 'config-button', 'index': ALL}, 'n_clicks'),
        Input({'type': 'placeholder-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        State('sci-notation-store', 'data'),
        prevent_initial_call=True
    )
    def update_active_panel(config_clicks, placeholder_clicks, panel_states_json, sci_notation_pref):
        """Updates the sidebar controls to match the selected panel."""
        triggered_id = ctx.triggered_id
        if not triggered_id: return no_update
            
        active_panel_index = triggered_id['index']
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(active_panel_index))
        
        # Defaults if panel is empty
        r1, r2, r3 = 'A', 'A', 'A'
        inv1, inv2 = 'tau_NA', 'tau_AC'
        log_scale = True
        colormap = 'Custom Rainbow'
        focus_pos = 1
        
        if state:
            triplet = state.get('triplet', 'AAA')
            if len(triplet) == 3:
                r1, r2, r3 = triplet[0], triplet[1], triplet[2]
            inv1 = state.get('inv1', 'tau_NA')
            inv2 = state.get('inv2', 'tau_AC')
            log_scale = state.get('log_scale', True)
            colormap = state.get('colormap', 'Custom Rainbow')
            focus_pos = state.get('focus_pos', 1)

        # Determine outline state based on loaded focus_pos
        f1_outline = (focus_pos != 1)
        f2_outline = (focus_pos != 2)
        f3_outline = (focus_pos != 3)

        return (
            active_panel_index, 
            f"Configure Panel {active_panel_index + 1}", 
            r1, r2, r3,
            inv1, inv2,
            log_scale, 
            colormap, 
            sci_notation_pref or False,
            f1_outline, f2_outline, f3_outline, focus_pos
        )

    # --- 3. Scientific Notation Preference ---
    @app.callback(
        Output('sci-notation-store', 'data'),
        Input('sci-notation-switch', 'value')
    )
    def update_sci_notation_store(switch_value):
        return switch_value

    # --- 4. Toggle View (Graph <-> Stats) ---
    @app.callback(
        Output('panel-states-store', 'data', allow_duplicate=True),
        Input({'type': 'toggle-view-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def toggle_panel_view(toggle_clicks, panel_states_json):
        triggered_id = ctx.triggered_id
        if not triggered_id or not any(c for c in toggle_clicks if c is not None): return no_update
        
        panel_index = triggered_id['index']
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(panel_index))
        
        if not state: return no_update
        
        # Flip view state
        current = state.get('view', 'graph')
        state['view'] = 'stats' if current == 'graph' else 'graph'
        
        panel_states[str(panel_index)] = state
        return json.dumps(panel_states)

    # --- 5. Focus Modal (Fullscreen View) ---
    @app.callback(
        Output('focus-modal', 'is_open'), 
        Output('focus-modal-header-title', 'children'),
        Output('focus-modal-body', 'children'),
        Input({'type': 'focus-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        State('sci-notation-store', 'data'),
        prevent_initial_call=True
    )
    def open_focus_modal(focus_clicks, panel_states_json, sci_notation_pref):
        triggered_id = ctx.triggered_id
        if not triggered_id or not any(c for c in focus_clicks if c is not None): return no_update, no_update, no_update
        
        panel_index = triggered_id['index']
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(panel_index))
        
        if not state: return no_update
        
        modal_title = f"Focus View: {state.get('title')}"
        view = state.get('view', 'graph')
        
        if view == 'graph':
            fig = create_3D_figure(
                state.get('figure_data'), '', state.get('uirevision_key'),
                state.get('log_scale'), state.get('colormap'), 
                state.get('x_lims'), state.get('y_lims')
            )
            content = dcc.Graph(figure=fig, style={'height': '100%'})
        else:
            # Re-render the full stats table in the modal
            content = build_comprehensive_stats(state.get('full_stats'), sci_notation_pref)
            
        return True, modal_title, content

    # --- 6. Clear Modal Logic ---
    @app.callback(
        Output('confirm-clear-modal', 'is_open'), 
        Output('last-clicked-panel-store', 'data'),
        Input({'type': 'clear-button', 'index': ALL}, 'n_clicks'),
        State('confirm-clear-modal', 'is_open'), 
        prevent_initial_call=True
    )
    def open_clear_modal(clear_clicks, is_open):
        triggered_id = ctx.triggered_id
        if not triggered_id or not any(clear_clicks): return no_update
        return True, triggered_id['index']

    @app.callback(
        Output('panel-states-store', 'data', allow_duplicate=True), 
        Output('confirm-clear-modal', 'is_open', allow_duplicate=True),
        Output('status-message-store', 'data', allow_duplicate=True),
        Input('confirm-clear-button', 'n_clicks'), 
        Input('cancel-clear-button', 'n_clicks'),
        State('last-clicked-panel-store', 'data'), 
        State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def handle_clear_confirmation(confirm, cancel, panel_index, panel_states_json):
        if ctx.triggered_id == 'cancel-clear-button' or panel_index is None: return no_update, False, no_update
        
        panel_states = json.loads(panel_states_json or '{}')
        if str(panel_index) in panel_states:
            del panel_states[str(panel_index)]
            return json.dumps(panel_states), False, f"Panel {panel_index + 1} cleared."
        return no_update, False, no_update

    # --- 7. Status Indicator ---
    @app.callback(
        Output('status-indicator', 'children'), 
        Output('status-indicator', 'style'),
        Output('status-clear-interval', 'disabled'), 
        Input('status-message-store', 'data'),
        State('status-indicator', 'style')
    )
    def update_status_indicator(message, style):
        if not message: 
            style['opacity'] = 0
            return "", style, True
        style['opacity'] = 1
        return message, style, False

    @app.callback(
        Output('status-message-store', 'data', allow_duplicate=True),
        Input('status-clear-interval', 'n_intervals'), 
        prevent_initial_call=True
    )
    def clear_status_message(n): return ""

    # --- 8. Download Stats CSV ---
    @app.callback(
        Output("download-html", "data"),
        Input({'type': 'download-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def download_stats(n_clicks, panel_states_json):
        triggered_id = ctx.triggered_id
        if not triggered_id or not any(n_clicks): return no_update
        
        panel_index = triggered_id['index']
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(panel_index))
        
        if not state or not state.get('full_stats'): return no_update
        
        # Create CSV in memory
        stats = state['full_stats']
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Metric', 'Value'])
        
        # Iterate over the 77 metrics
        for key, val in stats.items():
            writer.writerow([key, val])
            
        triplet = state.get('triplet', 'stats')
        focus = state.get('focus_pos', 1)
        filename = f"{triplet}_focus{focus}_stats.csv"
        
        return dict(content=output.getvalue(), filename=filename, type="text/csv")