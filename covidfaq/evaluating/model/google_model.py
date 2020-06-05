import codecs
import json
import logging
import operator
import os

import pandas as pd
import requests
import urllib3
from IPython.utils import io

from covidfaq.evaluating.model.model_evaluation_interface import (
    ModelEvaluationInterface,
)

logger = logging.getLogger(__name__)


project = 'descartes-covid'
model = 'hotline'


class GoogleModel(ModelEvaluationInterface):
    def __init__(self):
        # Export your gcloud auth token to an env variable:
        # export GCLOUD_AUTH_TOKEN=$(gcloud auth application-default print-access-token)
        self.gcloud_auth_token = os.environ["GCLOUD_AUTH_TOKEN"]
        self.headers = {"Authorization": "Bearer " + self.gcloud_auth_token}
        self.url = "https://ml.googleapis.com/v1/projects/descartes-covid/models/hotline:predict?alt=json"

        self.failed_attempts = 0

    def collect_answers(self, answers):

        answers_list = []
        for ans in answers:
            answers_list.append(ans[1])

        self.data = {"instances": [{"candidates": answers_list}]}

    def answer_question(self, question):

        self.data["instances"][0]["input"] = question
        post_data = json.dumps(self.data)
        response = requests.post(self.url, data=post_data, headers=self.headers)
        if response.status_code == 200:
            predictions = response.json()

            scores_list = [
                pred["similarity_score"] for pred in predictions["predictions"]
            ]
            index, value = max(enumerate(scores_list), key=operator.itemgetter(1))

            return index
        else:
            self.failed_attempts += 1
            logger.info(
                "Something went wrong when making the request. Total wrong requests:  {}".format(
                    self.failed_attempts
                )
            )
            return -1

pd.set_option('display.max_columns', None)
pd.set_option('display.expand_frame_repr', False)
pd.set_option('display.max_colwidth', None)


def IssueRpc(body):
    http = urllib3.PoolManager()
    rest_url = 'https://ml.googleapis.com/v1/projects/%s/models/%s:predict?alt=json' % (project, model)
    with io.capture_output() as captured:
        r = http.request(
                'POST',
                rest_url,
                body=json.dumps(body).encode('utf-8'),
                headers={                 
                        'Accept-Encoding': 'gzip',
                        'Content-Type': 'application/json',
                        'Authorization': 'Bearer ' + os.environ["GCLOUD_AUTH_TOKEN"]
                },
                preload_content=False)
    try:
        reader = codecs.getreader('utf-8')
        response = json.load(reader(r))
        if r.status == 200: 
            return response
        else:
            print(response)
    except json.JSONDecodeError:
        print("Error in reading HTTP response data... possibly truncated")


def Predict(input, candidates=[]):
    # Get access_token
    body = {
        'instances' : [{"input": input, "extra_candidate": candidates}]
    }
    response = IssueRpc(body)
    return [(s['candidate_question'], s['similarity_score']) for s in response['predictions']]


def DumpQuestion():
    body = {
        'signature_name' : 'get_cached_question',
        'instances' : [{"dummy": ''}]
    }
    response = IssueRpc(body)
    return response['predictions']


# Util functions to display mathcing questions and scores
TEMPLATE = '''matched_question': %s
match_score: %f
'''
def FindBestQA(query, candidates=[]):
    return Predict(query.rstrip('?'), candidates)[:5]


def PrintBestQA(query, candidates=[]):
    print("user_query: %s" % query)
    print("-" * 50)
    for best_question, best_score in FindBestQA(query, candidates):
        print(TEMPLATE % (best_question, best_score))


if __name__ == "__main__":
    query = "can my Dog transmit the coronavirus to me"  # @param {type:"string"}
    # candidate = "what is the main symptom of covid-19" #@param {type: "string"}

    candidates = ['answer number 1', 'answer number 2']

    PrintBestQA(query, [])
