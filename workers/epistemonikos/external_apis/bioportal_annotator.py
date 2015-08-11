#!/usr/bin/env python
# -*- coding: utf-8 -*-

#req:
#end req
import os
import re

import requests

import poliglo

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_TYPE = 'bioportal_annotator'

def _make_api_call(url, params=None):
    """Generic method to make calls to an API requiring a key."""
    if params is None:
        params = {}

    # params['apikey'] = CONFIG.BIOPORTAL_API_KEY
    params['apikey'] = "8316a8aa-ff8e-4d6e-aa95-faeabfc72d2a"
    return requests.get(url, params=params)

def _get_raw_annotations_for_text(text, ontologies='MESH', semantic_types=None):
    """Gets annotations from bioportal, for the given text, ontologies
    and semantic types."""

    if semantic_types is None:
        semantic_types = ()

    params = {}
    params['text'] = text
    params['ontologies'] = ontologies
    params['semantic_types'] = ','.join(semantic_types)
    response = _make_api_call('http://data.bioontology.org/annotator', params)
    raw_annotations = response.json()
    return raw_annotations

def get_annotation_quote(annotation_class_url, debug=False):
    results = {'status': 'ERROR', 'data': {}}

    if debug:
        print "bioportal.get_annotation_quote: %s" % annotation_class_url

    response = _make_api_call(annotation_class_url)
    resource = response.json()

    results['data'] = {
        'id': re.sub(r'.*/([A-Z0-9]+)$', r'\1', resource['@id']),
        'quote': resource['prefLabel']
    }
    results['status'] = 'OK'
    return results

def get_annotations_for_text(text, ontologies='MESH', semantic_types=(), debug=False):
    """Returns a list of annotations for the given text."""
    results = {'status': 'ERROR', 'data': []}

    if debug:
        print "bioportal.get_annotations_for_text"

    annotations = _get_raw_annotations_for_text(
        text,
        ontologies=ontologies,
        semantic_types=semantic_types
    )

    if not isinstance(annotations, list):
        results['message'] = 'BioPortal get annotations: Invalid format annotations'
        return results

    for annotation in annotations:
        ontology_data = re.findall(
            r'.*/([A-Z0-9]+)/([A-Z0-9]+)$', annotation['annotatedClass']['@id']
        ) or []

        info = {
            'id': annotation['annotatedClass']['@id'],
            'class': annotation['annotatedClass']['links']['self'],
            'frequency': len(annotation['annotations']),
            'matched_terms': list(
                set([an.get('text').lower() for an in annotation.get('annotations')])
            )
        }

        if len(ontology_data) == 1:
            info['ontology_type'] = ontology_data[0][0]
            info['ontology_quote_id'] = ontology_data[0][1]

        results['data'].append(info)

    results['status'] = 'OK'
    return results

def process(specific_info, data, *args):
    inputs = poliglo.get_inputs(data, specific_info)

    fields = inputs.get('fields', [])
    text = (" ".join([inputs.get(field) or "" for field in fields])).lower()

    annotated_data = get_annotations_for_text(text)
    return [{'bioportal_annotated': annotated_data},]

def main():
    poliglo.default_main(POLIGLO_SERVER_URL, WORKER_TYPE, process)

if __name__ == '__main__':
    main()
