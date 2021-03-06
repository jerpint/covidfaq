import os
import pickle

import numpy as np
import torch
import yaml
from structlog import get_logger
from yaml import load

from covidfaq.evaluating.model.embedding_based_reranker import EmbeddingBasedReRanker

log = get_logger()


def fit_OOD_detector(ret_trainee, hyper_params, lang="en", faq_json_file=None):
    """
    Prepare the best possible dataset for fitting the OOD model
    and fit on that dataset.
    The dataset consists of all crowdsourced questions that still
    exist in the new FAQ scrape.
    Here, we extract all the crowdsourced questions that align with the
    latest scrape, compute their embeddings using BERT
    and then fit the OOD model on the result.
    """
    from covidfaq.evaluating.model.bert_plus_ood import get_latest_scrape
    from bert_reranker.data.predict import generate_embeddings
    from bert_reranker.models.sklearn_outliers_model import fit_sklearn_model
    from bert_reranker.scripts.filter_user_questions import filter_user_questions

    if not faq_json_file:
        faq_data, faq_json_file = get_latest_scrape(lang=lang)

    all_question_embs = []
    faq_questions_set = set(
        [passage["reference"]["section_headers"][0] for passage in faq_data["passages"]]
    )

    # get the crowdsourced questions that align with the new scrape
    for user_question_file in hyper_params["outlier"]["training_data_files"]:
        user_json_data = filter_user_questions(user_question_file, faq_questions_set)

        embeddings_dict = generate_embeddings(
            ret_trainee, json_data=user_json_data, embed_passages=False
        )
        all_question_embs.extend(embeddings_dict["question_embs"])

    # get the questions directly from the scrape
    embeddings_dict = generate_embeddings(
        ret_trainee, json_data=faq_data, embed_passages=True
    )
    all_question_embs.extend(embeddings_dict["passage_header_embs"])

    # Fit the new OOD model on all the questions
    clf = fit_sklearn_model(
        all_question_embs,
        model_name=hyper_params["outlier"]["model_name"],
        output_filename="covidfaq/bert_" + lang + "_model/" + lang + "_ood_model.pkl",
        n_neighbors=4,
    )
    return clf


class EmbeddingBasedReRankerPlusOODDetector(EmbeddingBasedReRanker):
    def __init__(self, config, lang):
        super(EmbeddingBasedReRankerPlusOODDetector, self).__init__(config)
        with open(config, "r") as stream:
            hyper_params = load(stream, Loader=yaml.FullLoader)

        self.lang = lang
        self.hyper_params = hyper_params

        # If a model exists, load it, otherwise fit it on the new scrape
        ood_filename = hyper_params["outlier"]["ood_filename"]
        if os.path.isfile(ood_filename):
            log.info("Loading pretrained sklearn OOD model, not fitting on newest data")
            with open(ood_filename, "rb") as file:
                outlier_detector_model = pickle.load(file)
            self.outlier_detector_model = outlier_detector_model
        else:
            log.info("Fitting the sklearn OOD model on the latest data...")
            self.outlier_detector_model = fit_OOD_detector(
                self.ret_trainee, hyper_params, self.lang
            )

    def collect_answers(self, source2passages):
        if os.path.isfile(self.hyper_params.get("source2embedded_passages")):
            log.info("Loading precomputed passage embeddings")
            self.source2embedded_passages = torch.load(
                self.hyper_params["source2embedded_passages"]
            )
        else:
            log.info("Computing passage embeddings")
            out_file = (
                "covidfaq/bert_"
                + self.lang
                + "_model/"
                + self.lang
                + "_source2embedded_passages.tar"
            )
            super(EmbeddingBasedReRankerPlusOODDetector, self).collect_answers(
                source2passages, out_file=out_file
            )

    def answer_question(self, question, source):
        emb_question = self.ret_trainee.retriever.embed_question(question)
        in_domain = self.outlier_detector_model.predict(emb_question)
        in_domain = np.squeeze(in_domain)
        if in_domain == 1:
            return super(EmbeddingBasedReRankerPlusOODDetector, self).answer_question(
                emb_question, source, already_embedded=True
            )
        else:
            # for OOD, we return the index -1, and se set the score to 1.0
            return -1
