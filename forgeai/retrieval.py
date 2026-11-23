from types import SimpleNamespace
import numpy as np
from rank_bm25 import BM25Okapi

from forgeai.llm import embed


class HybridRetriever:
    def __init__(self, chunks, top_k=4, hybrid=True):
        self.chunks = chunks
        self.top_k = top_k
        self.hybrid = hybrid

        if not chunks:
            raise ValueError("No document chunks provided.")

        self.texts = [chunk["text"] for chunk in chunks]

        # Prepare keyword search
        tokenized = [text.lower().split() for text in self.texts]
        self.bm25 = BM25Okapi(tokenized)

        # Prepare semantic search
        self.embeddings = np.array(embed(self.texts), dtype=float)
        self.embeddings = self._normalize(self.embeddings)

    @staticmethod
    def _normalize(matrix):
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.maximum(norms, 1e-10)

    def search(self, query):
        # Keyword scores
        tokens = query.lower().split()
        keyword_scores = np.array(self.bm25.get_scores(tokens))

        # Semantic scores
        query_embedding = np.array(embed([query])[0], dtype=float)
        query_embedding = self._normalize(query_embedding.reshape(1, -1))[0]

        semantic_scores = self.embeddings @ query_embedding

        if self.hybrid:
            keyword_scores = keyword_scores / (
                np.max(keyword_scores) + 1e-10
            )
            semantic_scores = (
                semantic_scores - np.min(semantic_scores)
            ) / (
                np.max(semantic_scores) - np.min(semantic_scores) + 1e-10
            )

            scores = 0.4 * keyword_scores + 0.6 * semantic_scores
        else:
            scores = semantic_scores

        best_indices = np.argsort(scores)[::-1][:self.top_k]

        results = []

        for index in best_indices:
            result = self.chunks[index].copy()
            result["score"] = float(scores[index])
            results.append(result)

        return results
class Index(HybridRetriever):

    def search(self, query, top_k=4, hybrid=True):
        self.top_k = top_k
        self.hybrid = hybrid

        results = super().search(query)

        return [
            (
                SimpleNamespace(
                    doc=result["source"],
                    page=result["page"],
                    text=result["text"]
                ),
                result["score"]
            )
            for result in results
        ]