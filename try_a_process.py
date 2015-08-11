import poliglo
import requests
import json
from random import randint

def main():
    master_mind_url = "http://poliglo.epistemonikos.org:36756"

    script_id = 'check_search_accuracy'
    process_name = 'Check search accuracy'
    data = {
        'matrix_id': '55143ba518d84e42b3d98a72',
        'to_find_phrases': {
            'p': ['cap', 'community-acquired', 'pulmonary', 'pneumonia'],
            'i': ['hydrocortisone', 'pneumococcal', 'corticosteroid', 'corticosteroids'],
            'c': []
        }
    }


    all_data = {
        'name': process_name + " " + str(randint(0, 10000000)),
        'data': data
    }
    url = '%s/scripts/%s/processes' %(master_mind_url, script_id)
    print url
    print requests.post(
        url,
        data=json.dumps(all_data),
        headers={'content-type':'application/json'}
    )

main()
