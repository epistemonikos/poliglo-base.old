#!/usr/bin/env python
# -*- coding: utf-8 -*-

#req:
# requests
#end req

import os
import re
import math
import requests
import json
from operator import itemgetter

from poliglo import default_main, get_inputs, select_dict_el, make_request, to_json, json_loads, get_config, get_connection

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_TYPE = 'group_tfidf'

# TODO move bioportal to another worker
def process(specific_info, data, *args):
    inputs = get_inputs(data, specific_info)

    tfidf_worker_id = inputs.get('tfidf_worker_id')
    queue = inputs.get('__read_from_queue')
    connection = args[0].get('connection')
    all_words = {}

    all_data = [] #for bioportal

    if queue:
        queue_values = connection.zrange(queue, 0, -1)
        for queue_raw_data in queue_values:
            queue_data = json_loads(queue_raw_data)
            all_data.append(queue_data) #for bioportal

            tfidf = select_dict_el(queue_data, 'workers_output.%s.tfidf' % tfidf_worker_id)
            for word, value in tfidf:
                if not all_words.get(word):
                    all_words[word] = []
                all_words[word].append(value)

    max_apperance = max([len(values) for (word, values) in all_words.iteritems()])/5
    tfidf_results = [(word, 1.0*sum(values)/len(values)*0.65 + 0.35*min(len(values)/max_apperance, 1)) for (word, values) in all_words.iteritems()]
    tfidf_results.sort(key=lambda tup: -tup[1])

    # Bioportal
    bioportal_worker_id = inputs.get('bioportal_worker_id')
    bioportal_mesh_names_url = inputs.get('bioporta_mesh_names_url')
    mesh_names = json_loads(requests.get(bioportal_mesh_names_url).content)
    bioportal_merged = {}
    for queue_data in all_data:
        bioportal_annotated = select_dict_el(queue_data, 'workers_output.%s.bioportal_annotated' % bioportal_worker_id)
        for mesh_data in bioportal_annotated.get('data'):
            ontology_id = mesh_data.get('ontology_quote_id')
            if not bioportal_merged.get(ontology_id):
                if not mesh_names.get(ontology_id):
                    continue
                bioportal_merged[ontology_id] = {
                    'ontology_quote_id': ontology_id,
                    'matched_terms': [],
                    'total_frequency': 0,
                    'included_in_documents': 0,
                    'name': mesh_names.get(ontology_id)
                }
            bioportal_merged[ontology_id]['total_frequency'] += mesh_data.get('frequency')
            bioportal_merged[ontology_id]['included_in_documents'] += 1
            bioportal_merged[ontology_id]['matched_terms'] = list(set(mesh_data.get('matched_terms')+bioportal_merged[ontology_id]['matched_terms']))
    to_return_bioportal = sorted(
        bioportal_merged.values(), key=lambda k: k['included_in_documents'], reverse=True
    )
    return [{'group_tfidf': tfidf_results, 'bioportal_merged': to_return_bioportal},]


def main():
    config = get_config(POLIGLO_SERVER_URL, 'all')
    connection = get_connection(config)
    default_main(POLIGLO_SERVER_URL, WORKER_TYPE, process, {'connection': connection})

if __name__ == '__main__':
    main()
