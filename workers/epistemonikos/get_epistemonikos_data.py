#!/usr/bin/env python
# -*- coding: utf-8 -*-

#req:
# pymongo
# requests
#end req

import os
from operator import itemgetter
from bson.objectid import ObjectId

from pymongo import MongoClient
import requests

from poliglo import default_main, get_inputs, get_config, select_dict_el

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_TYPE = 'get_epistemonikos_data'

def to_unicode(text):
    if isinstance(text, unicode):
        return text
    elif isinstance(text, (int, long, float, complex)):
        return str(text).decode('utf-8')
    return unicode(text, 'utf-8')

def process(specific_info, data, *args):
    inputs = get_inputs(data, specific_info)
    mongo_connection = args[0].get('mongo_connection')

    data_filter = inputs.get('data_filter', {})
    fields = inputs.get('fields', [])
    names = inputs.get('names', [])
    collection = inputs.get('collection', [])
    target_file = inputs.get('target_file')
    data_selector = dict([(field, 1) for field in fields])

    matrix_id = inputs.get('matrix_id')

    if matrix_id:
        matrix_documents = set()
        matrix = mongo_connection.matrix.find_one({'_id': ObjectId(inputs.get('matrix_id'))})
        matrix_documents |= set([
            matrix_el.get('id') for matrix_el in select_dict_el(matrix, 'matrix_dict.matrix', [])
        ])
        matrix_documents |= set([
            matrix_el.get('id')
            for matrix_el in select_dict_el(matrix, 'matrix_dict.studies_order', [])
        ])
        data_filter.update({"id": {"$in": list(matrix_documents)}})

    if target_file:
        target_file = open(target_file, 'w')
        target_file.write("\t".join(names)+"\n")

    for episte_data in mongo_connection[collection].find(data_filter, data_selector):
        if target_file:
            text = u"\t".join([
                to_unicode(
                    select_dict_el(episte_data, field) or ''
                ).replace('\r\n', ' ').replace('\n', '').replace('\t', ' ') for field in fields
            ]).encode('utf-8')
            target_file.write(text+"\n")
        else:
            yield dict(
                [
                    (names[i], (select_dict_el(episte_data, field) or ''))
                    for i, field in enumerate(fields)
                ]
            )
    if target_file:
        yield {'episte_data_target_file': inputs.get('target_file')}

def main():
    config = get_config(POLIGLO_SERVER_URL, WORKER_TYPE)
    mongo_connection = MongoClient(config.get('MONGO_URI'))[config.get('MONGO_DB')]

    default_main(POLIGLO_SERVER_URL, WORKER_TYPE, process, {'mongo_connection': mongo_connection})

if __name__ == '__main__':
    main()

# TEST
from unittest import TestCase
from mock import Mock

class TestGetPage(TestCase):
    def setUp(self):
        self.specific_info = {
            'default_inputs': {
                'collection': 'documents',
            }
        }
        self.database = {'documents': Mock()}
        self.database['documents'].find.side_effect = [
            (
                {'id': 1, 'languages': {'en': {'abstract': 'abstract 0', 'title': 'title 0'}}},
                {'id': 2, 'languages': {'en': {'abstract': 'abstract 1', 'title': 'title 1'}}}
            )
        ]
        self.args = {'mongo_connection': self.database}

    def test_get_documents(self):
        data = {
            'process': {
                'type': 'example'
            },
            'inputs': {
                'data_filter': {'info.classification': 'systematic-review'},
                'fields': ['languages.en.title', 'id', 'languages.en.abstract'],
                'names': ['title', 'id', 'abstract'],
                'target_file': '/tmp/documents.tsv'
            }
        }
        results = list(process(self.specific_info, data, self.args))

        self.assertEqual('/tmp/documents.tsv', results[0].get('target_file'))
        lines = open('/tmp/documents.tsv').readlines()
        self.assertEqual(3, len(lines))
        self.assertEqual("title\tid\tabstract\n", lines[0])
        self.assertEqual("title 0\t1\tabstract 0\n", lines[1])

    def test_get_documents_with_yield(self):
        data = {
            'process': {
                'type': 'example'
            },
            'inputs': {
                'data_filter': {'info.classification': 'systematic-review'},
                'fields': ['languages.en.title', 'id', 'languages.en.abstract'],
                'names': ['title', 'id', 'abstract']
            }
        }
        results = list(process(self.specific_info, data, self.args))
        self.assertEqual({'abstract': 'abstract 0', 'id': 1, 'title': 'title 0'}, results[0])

