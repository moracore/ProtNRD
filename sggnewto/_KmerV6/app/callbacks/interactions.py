import json
import plotly.io as pio
from dash import dcc, html, Input, Output, State, no_update, ctx, ALL
import dash_bootstrap_components as dbc
# Import rendering functions to re-create figures for focus/download
from .rendering import create_3D_figure, create_1D_histo_figure
from constants import INVARIANT_SHORTHAND, TORSION_INVARIANTS

def register_interaction_callbacks(app):

    @app.callback(
        Output('xaxis-limit-label', 'children'),
        Output('yaxis-limit-label', 'children'),
        Input('inv1-dropdown', 'value'),
        Input('inv2-dropdown', 'value')
    )
    def update_axis_labels(inv1, inv2):
        """
        Updates the X and Y axis limit labels in the sidebar to match
        the selected invariants.
        """
        inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1)
        inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2)
        
        xaxis_text = f"{inv1_label}-axis limits"
        yaxis_text = f"{inv2_label}-axis limits"
        
        return xaxis_text, yaxis_text

    @app.callback(
        Output('active-panel-store', 'data'),
        Output('active-panel-display', 'children'),
        Output('inv1-dropdown', 'value'),
        Output('inv2-dropdown', 'value'),
        Output('offset-dropdown', 'value'),
        Output('res1-dropdown', 'value'),
        Output('res2-dropdown', 'value'),
        Output('xaxis-min-input', 'value'),
        Output('xaxis-max-input', 'value'),
        Output('yaxis-min-input', 'value'),
        Output('yaxis-max-input', 'value'),
        # Listen to clicks on the graph headers
        Input({'type': 'graph-header', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        State('active-panel-store', 'data'),
        prevent_initial_call=True
    )
    def update_active_panel(header_clicks, panel_states_json, current_active_index):
        # This callback now uses the graph-header to activate a panel
        triggered_id = ctx.triggered_id
        
        active_panel_index = current_active_index
        if triggered_id:
            active_panel_index = triggered_id['index']
        
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(active_panel_index))

        # Load state or defaults
        inv1 = state.get('inv1', 'tau_NA') if state else 'tau_NA'
        inv2 = state.get('inv2', 'tau_AC') if state else 'tau_AC'
        offset = state.get('offset', 0) if state else 0
        res1 = state.get('res1', 'Any') if state else 'Any'
        res2 = state.get('res2', 'Any') if state else 'Any'
        x_lims = state.get('x_lims', [None, None]) if state else [None, None]
        y_lims = state.get('y_lims', [None, None]) if state else [None, None]

        return (
            active_panel_index,
            f"Configure Panel {active_panel_index + 1}",
            inv1, inv2, offset, res1, res2,
            x_lims[0], x_lims[1], y_lims[0], y_lims[1]
        )

    @app.callback(
        Output('confirm-clear-modal', 'is_open'),
        Output('last-clicked-panel-store', 'data'),
        Input({'type': 'clear-button', 'index': ALL}, 'n_clicks'),
        State('confirm-clear-modal', 'is_open'),
        prevent_initial_call=True
    )
    def open_clear_modal(clear_clicks, is_open):
        triggered_id = ctx.triggered_id
        if not triggered_id or is_open or not any(c for c in clear_clicks if c is not None):
            return no_update, no_update
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
    def handle_clear_confirmation(confirm_clicks, cancel_clicks, panel_index, panel_states_json):
        button_id = ctx.triggered_id.get('id') if isinstance(ctx.triggered_id, dict) else ctx.triggered_id
        if not button_id or panel_index is None:
            return no_update, no_update, no_update

        panel_states = json.loads(panel_states_json or '{}')

        if button_id == 'confirm-clear-button':
            if str(panel_index) in panel_states:
                del panel_states[str(panel_index)]
                return json.dumps(panel_states), False, f"Panel {panel_index + 1} cleared."

        return no_update, False, no_update


    @app.callback(
        Output('focus-modal', 'is_open'),
        Output('focus-modal-header', 'children'),
        Output('focus-graph', 'figure'),
        Input({'type': 'focus-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        State('scale-switch', 'value'),
        State('colormap-dropdown', 'value'),
        prevent_initial_call=True
    )
    def open_focus_modal(focus_clicks, panel_states_json, scale_bool, colormap):
        triggered_id = ctx.triggered_id
        if not triggered_id or not any(c for c in focus_clicks if c is not None):
            return no_update, no_update, no_update

        panel_index = triggered_id['index']
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(panel_index))

        # This logic checks for the original v6 job types
        job_type = state.get('job_type')
        if not state or (job_type != '3D_HEATMAP' and job_type != '1D_HISTO_VS_STATS' and job_type != '1D_STATS_VS_HISTO'):
            return no_update, no_update, no_update

        try:
            fig = no_update
            if job_type == '3D_HEATMAP':
                fig = create_3D_figure(
                    state.get('figure_data',{}), state.get('title', ''), state.get('uirevision_key',''),
                    scale_bool, colormap, state.get('inv1'), state.get('inv2'),
                    state.get('x_lims'), state.get('y_lims')
                )
            elif job_type == '1D_HISTO_VS_STATS':
                # Re-create 1D histo for inv1
                fig = create_1D_histo_figure(
                    state.get('figure_data_histo',{}), state.get('title', ''), state.get('inv1')
                )
            elif job_type == '1D_STATS_VS_HISTO':
                # Re-create 1D histo for inv2
                fig = create_1D_histo_figure(
                    state.get('figure_data_histo',{}), state.get('title', ''), state.get('inv2')
                )

            return True, state.get('title', 'Focus View'), fig
        except Exception as e:
            print(f"Error creating focus figure: {e}")
            return no_update, no_update, no_update

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
    def clear_status_message(n_intervals):
        return ""

    @app.callback(
        Output("download-html", "data"),
        Input({'type': 'download-button', 'index': ALL}, 'n_clicks'),
        State('panel-states-store', 'data'),
        State('scale-switch', 'value'),
        State('colormap-dropdown', 'value'),
        prevent_initial_call=True
    )
    def download_graph_html(download_clicks, panel_states_json, scale_bool, colormap):
        triggered_id = ctx.triggered_id
        if not triggered_id or not any(c for c in download_clicks if c is not None):
            return no_update

        panel_index = triggered_id['index']
        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(panel_index))

        # This logic checks for the original v6 job types
        job_type = state.get('job_type')
        if not state or (job_type != '3D_HEATMAP' and job_type != '1D_HISTO_VS_STATS' and job_type != '1D_STATS_VS_HISTO'):
            return no_update

        try:
            fig = None
            if job_type == '3D_HEATMAP':
                fig = create_3D_figure(
                    state.get('figure_data',{}), state.get('title', ''), state.get('uirevision_key',''),
                    scale_bool, colormap, state.get('inv1'), state.get('inv2'),
                    state.get('x_lims'), state.get('y_lims')
                )
            elif job_type == '1D_HISTO_VS_STATS':
                fig = create_1D_histo_figure(
                    state.get('figure_data_histo',{}), state.get('title', ''), state.get('inv1')
                )
            elif job_type == '1D_STATS_VS_HISTO':
                fig = create_1D_histo_figure(
                    state.get('figure_data_histo',{}), state.get('title', ''), state.get('inv2')
                )

            if fig:
                filename = f"{state.get('title', 'graph').replace(' ', '_').replace('+', '')}.html"
                return dict(content=pio.to_html(fig, full_html=True), filename=filename)

            return no_update
        except Exception as e:
            print(f"Error creating download figure: {e}")
            return no_update

    # --- NEW: Callbacks for Full Stats Modal ---

    @app.callback(
        Output('stats-modal', 'is_open'),
        Output('last-clicked-panel-store', 'data', allow_duplicate=True),
        Input({'type': 'open-stats-button', 'index': ALL}, 'n_clicks'),
        Input('close-stats-modal-button', 'n_clicks'),
        State('stats-modal', 'is_open'),
        prevent_initial_call=True
    )
    def toggle_stats_modal(open_clicks, close_clicks, is_open):
        """Opens or closes the stats modal."""
        triggered_id = ctx.triggered_id
        if not triggered_id:
            return no_update, no_update

        if 'open-stats-button' in triggered_id.type:
            # Save which panel triggered this modal
            return True, triggered_id['index']
        
        # Any other trigger (e.g., 'close-stats-modal-button') closes it
        return False, no_update

    @app.callback(
        Output('stats-modal-content', 'children'),
        Input('stats-modal', 'is_open'),
        State('last-clicked-panel-store', 'data'),
        State('panel-states-store', 'data'),
        prevent_initial_call=True
    )
    def populate_stats_modal(is_open, panel_index, panel_states_json):
        """Populates the stats modal with data from the correct panel."""
        if not is_open or panel_index is None:
            return no_update

        panel_states = json.loads(panel_states_json or '{}')
        state = panel_states.get(str(panel_index))
        
        # Get the full, untransformed v7 stats
        stats = state.get('full_v7_stats')
        inv1 = state.get('inv1')
        inv2 = state.get('inv2')
        inv1_label = INVARIANT_SHORTHAND.get(inv1, inv1)
        inv2_label = INVARIANT_SHORTHAND.get(inv2, inv2)

        if not stats:
            return dbc.Alert("Could not load statistics.", color="danger")

        # Helper to format stats
        fmt_f = lambda k, p=3: f"{stats.get(k, 0):.{p}f}" if stats.get(k) is not None else "N/A"
        fmt_i = lambda k: f"{stats.get(k, 0):,}" if stats.get(k) is not None else "N/A"
        
        # Build the table
        table_header = [
            html.Thead(html.Tr([html.Th("Statistic"), html.Th(inv1_label), html.Th(inv2_label)]))
        ]
        
        table_body = [
            html.Tbody([
                html.Tr([html.Td("Mean"), html.Td(fmt_f('mean_x')), html.Td(fmt_f('mean_y'))]),
                html.Tr([html.Td("Variance"), html.Td(fmt_f('variance_x')), html.Td(fmt_f('variance_y'))]),
                html.Tr([html.Td("Median"), html.Td(fmt_f('median_x')), html.Td(fmt_f('median_y'))]),
                html.Tr([html.Td("Min"), html.Td(fmt_f('min_x')), html.Td(fmt_f('min_y'))]),
                html.Tr([html.Td("Max"), html.Td(fmt_f('max_x')), html.Td(fmt_f('max_y'))]),
                html.Tr([html.Td("Freq. at Mean"), html.Td(fmt_i('freq_at_mean_x')), html.Td(fmt_i('freq_at_mean_y'))]),
            ])
        ]
        
        pair_stats = dbc.ListGroup([
            dbc.ListGroupItem(f"Population: {fmt_i('population')}"),
            dbc.ListGroupItem(f"Covariance: {fmt_f('covariance')}"),
            dbc.ListGroupItem(f"Peak Location (X, Y): ({fmt_f('peak_x', 2)}, {fmt_f('peak_y', 2)})"),
            dbc.ListGroupItem(f"Peak Frequency: {fmt_i('peak_freq')}"),
        ], flush=True, className="mt-3")

        return [
            dbc.Table(table_header + table_body, bordered=True, striped=True, hover=True),
            html.H5("Pairwise Stats", className="mt-4"),
            pair_stats
        ]