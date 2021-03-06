# -*- coding: utf-8 -*-

import dash_core_components as dcc
import dash_html_components as html

from umserver import app
from umserver.models import get_training_sessions

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dcc.Location(id='url-update', refresh=False),
    html.Div([
        html.H1('Umlaut Toolkit', style={'display': 'inline-block'}),
        dcc.Dropdown(
            id='session-picker',
            placeholder='Named Sessions',
            style={'width': 200, 'display': 'inline-block', 'float': 'right'},
        ),
        dcc.Graph(
            id='timeline',
            config={
                'displayModeBar': False,
                'watermark': False,
                'displaylogo': False,
            },
            figure={
                'layout': {
                    'height': 150,
                    'barmode': 'relative',
                    'hovermode': 'closest',
                    'bargap': 0.05,
                    'yaxis': {
                        'showgrid': False,
                        'zeroline': True,
                        'showticklabels': False,
                        'fixedrange': True,
                    },
                    'xaxis': {
                        'rangemode': 'nonnegative',
                        'fixedrange': True,
                    },
                    'margin': {
                        't': 0,
                        'b': 30,
                    }
                },
                'data': [],
            },
        ),
    ]),
    html.Div([
            html.H3('Visualizations'),
            dcc.Graph(
                id='graph_loss',
                figure={
                    'layout': {'title': 'Loss over Epochs'},
                },
            ),
            dcc.Graph(
                id='graph_acc',
                figure={
                    'layout': {'title': 'Accuracy over Epochs'},
                },
            ),
        ],
        className='five columns',
    ),
    html.Div([
            html.H3('Error Messages', style={'display': 'inline-block'}),
            html.Button(id='btn-clear-annotations', children='Clear Annotations', style={'display': 'inline-block', 'float': 'right'}),
            html.Hr(),
            html.Div(id='errors-list'),
        ],
        className='six columns',
    ),
    dcc.Interval(
	id='interval-component',
	interval=10*1000, # in milliseconds
	n_intervals=0,
    ),
    dcc.Store(id='metrics-cache', storage_type='memory'),
    dcc.Store(id='errors-cache', storage_type='memory'),
    dcc.Store(id='annotations-cache', storage_type='memory'),
])
