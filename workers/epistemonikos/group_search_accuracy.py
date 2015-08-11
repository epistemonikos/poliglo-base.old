#!/usr/bin/env python
# -*- coding: utf-8 -*-

#req:
#end req

import os
import json

from poliglo import default_main, get_inputs, json_loads, get_config, get_connection

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_TYPE = 'group_search_accuracy'

def process(specific_info, data, *args):
    inputs = get_inputs(data, specific_info)

    queue = inputs.get('__read_from_queue')
    connection = args[0].get('connection')

    to_return_data = {
        'phrases': {
            'matching': {},
            'not_matching': {}
        },
        'all_phrases': {
            'matching': [],
            'not_matching': []
        }
    }

    queue_values = connection.zrange(queue, 0, -1)
    for queue_raw_data in queue_values:
        queue_data = json_loads(queue_raw_data).get('inputs')
        match_all = True
        for phrase_group, phrase_value in queue_data.get('phrases', {}).iteritems():
            if phrase_value:
                target = 'matching'
            else:
                target = 'not_matching'
            if not to_return_data['phrases'][target].get(phrase_group):
                to_return_data['phrases'][target][phrase_group] = []
            if queue_data['doc_id'] not in to_return_data['phrases'][target][phrase_group]:
                to_return_data['phrases'][target][phrase_group].append(queue_data['doc_id'])
            match_all = match_all and phrase_value
        target = 'not_matching'
        if match_all:
            target = 'matching'
        if queue_data['doc_id'] not in to_return_data['all_phrases'][target]:
            to_return_data['all_phrases'][target].append(queue_data['doc_id'])

    return [to_return_data,]


def main():
    config = get_config(POLIGLO_SERVER_URL, 'all')
    connection = get_connection(config)
    default_main(POLIGLO_SERVER_URL, WORKER_TYPE, process, {'connection': connection})

if __name__ == '__main__':
    main()

# TEST
from unittest import TestCase
from mock import Mock

class TestGroupSearchAccuracy(TestCase):
    def setUp(self):
        self.specific_info = {
            'default_inputs': {
            }
        }
        self.queue = 'test_queue'
        self.connection = Mock()
        self.connection.zrange.return_value = [
            json.dumps({'inputs': {'doc_id': 'doc1', 'phrases': {'p': True, 'i': True, 'c': False}, 'all_phrases': False}}),
            json.dumps({'inputs': {'doc_id': 'doc2', 'phrases': {'p': True, 'i': True, 'c': True}, 'all_phrases': True}})
        ]
        self.args = {'connection': self.connection}

    def test_group_search(self):
        data = {
            'process': {
                'type': 'example'
            },
            'inputs': {
                '__read_from_queue': 'test_queue'
            }
        }
        results = list(process(self.specific_info, data, self.args))
        expected = {
            'phrases': {
                'matching': {
                    'p': ['doc1', 'doc2'],
                    'i': ['doc1', 'doc2'],
                    'c': ['doc2']
                },
                'not_matching': {
                    'c': ['doc1']
                }
            },
            'all_phrases': {
                'matching': ['doc2'],
                'not_matching': ['doc1']
            }
        }
        self.assertEqual(expected, results[0])

