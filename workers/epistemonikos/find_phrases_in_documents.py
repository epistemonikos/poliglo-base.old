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
WORKER_TYPE = 'find_phrases_in_documents'

def to_unicode(text):
    if isinstance(text, unicode):
        return text
    elif isinstance(text, (int, long, float, complex)):
        return str(text).decode('utf-8')
    return unicode(text, 'utf-8')

def process(specific_info, data, *args):
    inputs = get_inputs(data, specific_info)

    document_id = inputs.get('document_id')
    to_find_phrases = inputs.get('to_find_phrases', {})
    where_to_find = inputs.get('where_to_find', [])

    document_text = (" ".join([(inputs.get(where) or '') for where in where_to_find])).lower()

    to_return = {'doc_id': document_id, 'phrases': {}}
    found_all = True
    for phrase_group, phrases in to_find_phrases.iteritems():
        to_return['phrases'][phrase_group] = False
        for phrase in phrases:
            if document_text.find(phrase.lower()) >= 0:
                to_return['phrases'][phrase_group] = True
        found_all = found_all and to_return['phrases'][phrase_group]
    to_return['all_phrases'] = found_all
    return [to_return]

def main():
    config = get_config(POLIGLO_SERVER_URL, WORKER_TYPE)
    mongo_connection = MongoClient(config.get('MONGO_URI'))[config.get('MONGO_DB')]

    default_main(POLIGLO_SERVER_URL, WORKER_TYPE, process, {'mongo_connection': mongo_connection})

if __name__ == '__main__':
    main()

# TEST
from unittest import TestCase

class TestGetPage(TestCase):
    def setUp(self):
        self.specific_info = {
            'default_inputs': {
                'where_to_find': ["title", "abstract"]
            }
        }

    def test_get_documents(self):
        data = {
            'process': {
                'type': 'example'
            },
            'inputs': {
                'document_id': 'doc1',
                'title': 'Corticosteroid Therapy for Severe Community-Acquired Pneumonia: A Meta-Analysis.',
                'abstract': """BACKGROUND: The debate about the efficacy of corticosteroids in the treatment of severe community- acquired pneumonia (CAP) is still a longstanding dilemma. We performed a meta-analysis including 4 randomized controlled trials (RCTs) to evaluate the effect of corticosteroids on the treatment of severe CAP in adults. METHODS: We performed a systematic review of published and unpublished clinical trials. Databases, including PubMed, Embase, CINAHL, and Cochrane (from their establishment to July 2013), were searched for relevant articles. Only RCTs of corticosteroids as adjunctive therapy in adult patients with severe CAP were selected. RESULTS: Four trials enrolling 264 patients with severe CAP were included. Use of corticosteroids significantly reduced hospital mortality compared with conventional therapy and placebo (Peto odds ratio = 0.39, 95% CI 0.17- 0.90). The quality of the evidence underlying the pooled estimate of effect on hospital mortality was low, downgraded for inconsistency and imprecision. CONCLUSIONS: On the basis of the current limited evidence, we suggest that, although corticosteroid therapy may reduce mortality and improve the prognosis of adult patients with severe CAP, the results should be interpreted with caution due to the instability of pooled estimates. Reliable treatment recommendations will be raised only when large sufficiently powered multi-center RCTs are conducted.""",
                'to_find_phrases': {
                    "p": ["pneumonia", "cap", "community-acquired"],
                    "i": ["hydrocortisone", "corticosteroids", "corticosteroid"],
                    "c": ["aspirine",]
                }
            }
        }
        results = list(process(self.specific_info, data))

        expected = {'doc_id': 'doc1', 'phrases': {'p': True, 'i': True, 'c': False}, 'all_phrases': False}
        self.assertEqual(expected, results[0])
