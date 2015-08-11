#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import math
import json
from operator import itemgetter

from poliglo import default_main, get_inputs, select_dict_el, make_request, to_json
from poliglo.utils import to_unicode

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_TYPE = 'tfidf'

STOPWORDS = ("a", "about", "above", "above", "across", "after", "afterwards", "again", "against", "all", "almost", "alone", "along", "already", "also", "although", "always", "am", "among", "amongst", "amoungst", "amount", "an", "and", "another", "any", "anyhow", "anyone", "anything", "anyway", "anywhere", "are", "around", "as", "at", "back", "be", "became", "because", "become", "becomes", "becoming", "been", "before", "beforehand", "behind", "being", "below", "beside", "besides", "between", "beyond", "bill", "both", "bottom", "but", "by", "call", "can", "cannot", "cant", "co", "con", "could", "couldnt", "cry", "de", "describe", "detail", "do", "done", "down", "due", "during", "each", "eg", "eight", "either", "eleven", "else", "elsewhere", "empty", "enough", "etc", "even", "ever", "every", "everyone", "everything", "everywhere", "except", "few", "fifteen", "fify", "fill", "find", "fire", "first", "five", "for", "former", "formerly", "forty", "found", "four", "from", "front", "full", "further", "get", "give", "go", "had", "has", "hasnt", "have", "he", "hence", "her", "here", "hereafter", "hereby", "herein", "hereupon", "hers", "herself", "him", "himself", "his", "how", "however", "hundred", "ie", "if", "in", "inc", "indeed", "interest", "into", "is", "it", "its", "itself", "keep", "last", "latter", "latterly", "least", "less", "ltd", "made", "many", "may", "me", "meanwhile", "might", "mill", "mine", "more", "moreover", "most", "mostly", "move", "much", "must", "my", "myself", "name", "namely", "neither", "never", "nevertheless", "next", "nine", "no", "nobody", "none", "noone", "nor", "not", "nothing", "now", "nowhere", "of", "off", "often", "on", "once", "one", "only", "onto", "or", "other", "others", "otherwise", "our", "ours", "ourselves", "out", "over", "own", "part", "per", "perhaps", "please", "put", "rather", "re", "same", "see", "seem", "seemed", "seeming", "seems", "serious", "several", "she", "should", "show", "side", "since", "sincere", "six", "sixty", "so", "some", "somehow", "someone", "something", "sometime", "sometimes", "somewhere", "still", "such", "system", "take", "ten", "than", "that", "the", "their", "them", "themselves", "then", "thence", "there", "thereafter", "thereby", "therefore", "therein", "thereupon", "these", "they", "thickv", "thin", "third", "this", "those", "though", "three", "through", "throughout", "thru", "thus", "to", "together", "too", "top", "toward", "towards", "twelve", "twenty", "two", "un", "under", "until", "up", "upon", "us", "very", "via", "was", "we", "well", "were", "what", "whatever", "when", "whence", "whenever", "where", "whereafter", "whereas", "whereby", "wherein", "whereupon", "wherever", "whether", "which", "while", "whither", "who", "whoever", "whole", "whom", "whose", "why", "will", "with", "within", "without", "would", "yet", "you", "your", "yours", "yourself", "yourselves", "the")

def tokenize(text):
    text = re.sub(r'[\b\(\)\\\"\'\/\[\]\s+\,\.:\?;]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.split()

def process(specific_info, data, *args):
    inputs = get_inputs(data, specific_info)

    idf = json.loads(open(inputs.get('idf_file')).read())

    text = (" ".join([inputs.get(field) for field in inputs.get('fields')])).lower()

    words_in_document = {}
    total_words = 0
    for word in tokenize(to_unicode(text)):
        if word in STOPWORDS:
            continue
        if not words_in_document.get(word):
            words_in_document[word] = 0
        words_in_document[word] += 1
        total_words += 1

    tfidf = []
    for word, word_count in words_in_document.iteritems():
        tfidf.append(
            (
                word,
                idf.get(word, 0) * (1.0*word_count/total_words)
            )
        )
    tfidf = sorted(tfidf, key=lambda tfidf_tuple: -tfidf_tuple[1])

    return [{'tfidf': tfidf},]


def main():
    default_main(POLIGLO_SERVER_URL, WORKER_TYPE, process)

if __name__ == '__main__':
    main()
