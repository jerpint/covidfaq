import json

from bert_reranker.data.data_loader import get_passages_by_source

from covidfaq.evaluating.model.embedding_based_reranker_plus_ood_detector import (
    EmbeddingBasedReRankerPlusOODDetector,
)


class BertPlusOOD:
    class __BertPlusOOD:
        def __init__(self):
            self.model = EmbeddingBasedReRankerPlusOODDetector(
                "covidfaq/bert_en_model/config.yaml"
            )
            with open(
                "covidfaq/bert_en_model/quebec_faq_en_cleaned_20200522.json", "r"
            ) as in_stream:
                test_data = json.load(in_stream)
            (
                self.source2passages,
                self.passage_id2source,
                self.passage_id2index,
            ) = get_passages_by_source(test_data)
            self.model.collect_answers(self.source2passages)

        def get_answer(self, question):
            idx_tensor = self.model.answer_question(
                question, "20200522_quebec_faq_en_cleaned_collection4"
            )
            if idx_tensor == -1:
                # we are out of distribution
                answer = []
            else:
                idx = idx_tensor.item()
                answer_dict = self.source2passages[
                    "20200522_quebec_faq_en_cleaned_collection4"
                ][idx]
                answer = answer_dict.get("reference").get("section_content")
                answer = [answer]

            return answer

    instance = None

    def __init__(self):
        if not BertPlusOOD.instance:
            BertPlusOOD.instance = BertPlusOOD.__BertPlusOOD()
        else:
            BertPlusOOD.instance.model = EmbeddingBasedReRankerPlusOODDetector(
                "covidfaq/bert_en_model/config.yaml"
            )
            with open(
                "covidfaq/bert_en_model/quebec_faq_en_cleaned_20200522.json", "r"
            ) as in_stream:
                test_data = json.load(in_stream)
            (
                BertPlusOOD.instance.source2passages,
                BertPlusOOD.instance.passage_id2source,
                BertPlusOOD.instance.passage_id2index,
            ) = get_passages_by_source(test_data)
            BertPlusOOD.instance.model.collect_answers(
                BertPlusOOD.instance.source2passages
            )

    def __getattr__(self, name):
        return getattr(self.instance, name)