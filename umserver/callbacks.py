# -*- coding: utf-8 -*-

import bson
import dash
import json
import random
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State, ALL, MATCH
from dash.exceptions import PreventUpdate
from bson import ObjectId
from flask import abort
from flask import request

from umserver import app
from umserver.errors import ERROR_KEYS
from umserver.helpers import argmax, index_of_dict
from umserver.models import db
from umserver.models import get_training_sessions


# ---------- Helper Functions for Rendering ---------- #


def get_go_data_from_metrics(plot, metrics_data):
    '''populate graph_figure.data from metrics_data'''
    return [  # make a plot for every plot stream
        {
            'x': metrics_data[plot][k][0],
            'y': metrics_data[plot][k][1],
            'name': k,
            'type': 'line+marker',
        } for k in metrics_data[plot]
    ]


def make_annotation_box_shape(x1):
    return {
        'type': 'rect',
        'xref': 'x',
        'yref': 'paper',
        'x0': x1 - 1,  # x0, x1 are epoch bounds
        'x1': x1,
        'y0': 0,
        'y1': 1,
        'fillcolor': 'LightPink',
        'opacity': 0.5,
        'layer': 'below',
        'line_width': 0,
    }


def render_error_message(id_in, error_message):
    return html.Div(
        [
            html.H3(error_message['title']),
            dcc.Markdown(error_message['description']),
            html.Small('Captured at epoch {}.'.format(error_message['epoch'])),
            html.Hr(),
        ],
        id=id_in,
        style={'cursor': 'pointer', 'display': 'inline-block'},
    )


# ---------- App Callbacks ---------- #

@app.callback(
    Output('session-picker', 'value'),
    [Input('url-update', 'pathname')],
)
def update_dropdown_from_url(pathname):
    '''set the dropdown value from a different url object

    Yes I know this is awful, but it works. This will make
    pages load from URL alone, populating the dropdown with
    a default value.
    '''
    if pathname and 'session' in pathname:
        path = pathname.split('/')
        # fetch session from URL: /session/session_id
        sess_id = path[path.index('session') + 1]
        return sess_id
    return pathname


@app.callback(
    Output('session-picker', 'options'),
    [Input('url-update', 'pathname')],
)
def update_dropdown_options(pathname):
    '''populate session picker from db on page load.
    '''
    return get_training_sessions()


@app.callback(
    Output('url', 'pathname'),
    [Input('session-picker', 'value')]
)
def change_url(ses):
    '''update URL based on session picked in dropdown'''
    if ses is '/':
        raise PreventUpdate
    # don't catch invalidId, let it error out
    return f'/session/{ObjectId(ses)}'


@app.callback(
    Output({'type': 'error-msg', 'index': ALL}, 'style'),
    [
        Input('annotations-cache', 'data'),
        Input('errors-cache', 'data'),
    ],
    [State({'type': 'error-msg', 'index': ALL}, 'style')],
)
def highlight_errors_from_annotations(annotations_cache, error_styles, errors_cache):
    for style in error_styles:
        style.pop('backgroundColor', None)
    if annotations_cache:
        for annotation in annotations_cache:
            error_styles[annotation['error-index']]['backgroundColor'] = 'LightPink'
    return error_styles


@app.callback(
    Output('annotations-cache', 'data'),
    [
        Input('errors-cache', 'data'),
        Input('btn-clear-annotations', 'n_clicks'),
        Input({'type': 'error-msg', 'index': ALL}, 'n_clicks'),
    ],
    [State('annotations-cache', 'data')],
)
def highlight_graph_for_error(error_msgs, clear_clicks, errors_clicks, annotations_cache):
    '''Update annotations state when an error message
    is clicked, or if the annotations are cleared.
    '''
    if not dash.callback_context.triggered:
        raise PreventUpdate

    # get the input that actually triggered this callback, and its id
    trigger = dash.callback_context.triggered[0]
    trigger_id = trigger['prop_id'].split('.')[0]
    if not trigger['value'] or trigger_id == 'errors-cache':
        # Trigger malformed or was just a cache update
        raise PreventUpdate

    # clear annotations button pressed, remove annotations
    if trigger_id == 'btn-clear-annotations':
        return []

    # trigger_id is...probably... a dict of the error-msg id
    trigger_id = eval(trigger_id)
    trigger_idx = trigger_id['index']  # error-msg.id.index

    if not error_msgs[trigger_idx].get('epoch', False):
        # no annotations associated with the clicked error
        return annotations_cache

    # if this error msg is already in annotations, pop it
    if annotations_cache:
        annotations_error_idx = index_of_dict(annotations_cache, 'error-index', trigger_idx)
        if annotations_error_idx is not None:
            annotations_cache.pop(annotations_error_idx)
            return annotations_cache
    else:
        annotations_cache = []
    
    clicked_error_annotation = {
        'error-index': trigger_idx,
        'indices': list(set(error_msgs[trigger_idx]['epoch'])),
    }
    annotations_cache.append(clicked_error_annotation)

    return annotations_cache


@app.callback(
    Output('metrics-cache', 'data'),
    [Input('interval-component', 'n_intervals'), Input('url', 'pathname')],
    [State('metrics-cache', 'data')],
)
def update_metrics_data(intervals, pathname, metrics_data):
    '''handle updates to the metrics data'''
    if intervals is None or pathname is None:
        raise PreventUpdate

    if pathname == '/':
        return {}
    path = pathname.split('/')
    # fetch session from URL: /session/session_id
    sess_id = path[path.index('session') + 1]
    try:
        session_plots = [s for s in db.plots.find(
            {'session_id': ObjectId(sess_id)})]
    except bson.errors.InvalidId:
        return {}

    go_data = {}
    for plot in session_plots:
        # this one liner unzips each stream from [[x, y], ...] to [[x, ...], [y, ...]]
        go_data[plot['name']] = {
            k: list(zip(*plot['streams'][k])) for k in plot['streams']
        }

    if go_data == metrics_data:
        # no difference after computing the plot data, don't rerender
        raise PreventUpdate

    return go_data


@app.callback(
    Output('errors-cache', 'data'),
    [Input('interval-component', 'n_intervals'), Input('url', 'pathname')],
    [State('errors-cache', 'data')],
)
def update_errors_data(interval, pathname, errors_data):
    '''Updates the errors cache by making an API call
    '''
    if interval is None or pathname is None:
        raise PreventUpdate

    if pathname == '/':
        return {}

    path = pathname.split('/')
    sess_id = path[path.index('session') + 1]
    try:
        errors_result = list(db.errors.find(
            {'session_id': ObjectId(sess_id)},
            # omit object ids from results, not json friendly
            {'_id': 0, 'session_id': 0},
        ).sort([('epoch', -1)]))  # sort by epoch descending (latest first)
    except bson.errors.InvalidId:
        abort(400)

    if errors_result == errors_data:
        # Errors haven't changed, don't rerender.
        raise PreventUpdate

    return errors_result


@app.callback(
    Output('errors-list', 'children'),
    [Input('errors-cache', 'data')],
)
def update_errors_list(errors_data):
    '''Renders errors from errors cache changes.
    '''
    result_divs = []

    if not errors_data:
        return html.P('No errors found for this session.')

    if len(errors_data) == 0:
        result_divs.append(html.P('No errors yay!'))

    for i, error_spec in enumerate(errors_data):
        result_divs.append(ERROR_KEYS[error_spec['error_id_str']](
            error_spec.get('epoch', None),
        ).render(
            {
                'type': 'error-msg',
                'index': i,
            },
        ))

    return result_divs


@app.callback(
    Output('graph_loss', 'figure'),
    [Input('metrics-cache', 'data'), Input('annotations-cache', 'data')],
)
def update_loss(metrics_data, annotations_data):
    if not metrics_data:
        return {}

    graph_figure = {
        'layout': {
            'title': 'Loss over epochs',
            'shapes': [],
        },
        'data': get_go_data_from_metrics('loss', metrics_data),
    }

    if annotations_data:
        for annotation in annotations_data:
            for idx in annotation['indices']:
                graph_figure['layout']['shapes'].append(
                    make_annotation_box_shape(idx)
                )

    return graph_figure


@app.callback(
    Output('graph_acc', 'figure'),
    [Input('metrics-cache', 'data'), Input('annotations-cache', 'data')],
)
def update_acc(metrics_data, annotations_data):
    if not metrics_data:
        return {}
    graph_figure = {
        'layout': {
            'title': 'Accuracy over epochs',
            'shapes': [],
        },
        'data': get_go_data_from_metrics('acc', metrics_data),
    }

    if annotations_data:
        for annotation in annotations_data:
            for idx in annotation['indices']:
                graph_figure['layout']['shapes'].append(
                    make_annotation_box_shape(idx)
                )

    return graph_figure


if __name__ == '__main__':
    app.run_server(host='0.0.0.0', port=8888, debug=True)
