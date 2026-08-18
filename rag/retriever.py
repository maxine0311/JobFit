"""Hybrid retriever: BM25 + dense vector search with RRF fusion, optional rerank."""

from __future__ import annotations

import json
import os
from typing import List, Optional

from rag.tokenizer import tokenize
from rag.vector_store import VectorStore


class Retriever:
    def __init__(
        self,
        chunks_json: str,
        vector_store: VectorStore,
        rerank_provider: str = "api",
        rerank_model: str = "BAAI/bge-reranker-v2-m3",
        rerank_api_key: str = "",
        rerank_base_url: str = "https://api.siliconflow.cn/v1",
    ):
        from rank_bm25 import BM25Okapi  # lazy import keeps tests dependency-free

        with open(chunks_json, "r", encoding="utf-8") as f:
            self.chunks: List[dict] = json.load(f)
        self.by_id = {c["id"]: c for c in self.chunks}
        self.vector_store = vector_store
        self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])
        self.rerank_provider = rerank_provider
        self.rerank_model = rerank_model
        self.rerank_api_key = rerank_api_key or os.getenv("EMBEDDING_API_KEY", "")
        self.rerank_base_url = rerank_base_url
        self.reranker = None
        if rerank_provider == "local" and rerank_model:
            try:
                from sentence_transformers import CrossEncoder

                self.reranker = CrossEncoder(rerank_model)
            except ImportError:
                print("[retriever] sentence-transformers not installed; rerank disabled.")

    # -- dense -----------------------------------------------------------
    def dense_topk(self, embedding: List[float], k: int) -> List[str]:
        ids, _ = self.vector_store.query(embedding, n_results=max(k, 1))
        return ids

    # -- sparse ----------------------------------------------------------
    def bm25_topk(self, query: str, k: int) -> List[str]:
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.chunks[i]["id"] for i in ranked[:k] if scores[i] > 0]

    # -- fusion ----------------------------------------------------------
    @staticmethod
    def _rrf(ranked_lists: List[List[str]], k: int = 60) -> List[str]:
        scores: dict[str, float] = {}
        for ranked in ranked_lists:
            for rank, doc_id in enumerate(ranked):
                scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (rank + k)
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [doc_id for doc_id, _ in ordered]

    def hybrid_topk(self, query: str, embedding: List[float], k: int, dense_weight: float = 0.5) -> List[str]:
        dense_ids = self.dense_topk(embedding, k=k)
        sparse_ids = self.bm25_topk(query, k=k)
        fused = self._rrf([dense_ids, sparse_ids])
        return fused[:k]

    # -- rerank ----------------------------------------------------------
    def rerank(self, query: str, doc_ids: List[str], k: int) -> List[str]:
        if not doc_ids:
            return doc_ids
        if self.rerank_provider == "api":
            return self._rerank_api(query, doc_ids, k)
        if not self.reranker:
            return doc_ids
        pairs = [(query, self.by_id[did]["text"][:512]) for did in doc_ids]
        scores = self.reranker.predict(pairs)
        ordered = sorted(zip(doc_ids, scores), key=lambda kv: kv[1], reverse=True)
        return [did for did, _ in ordered[:k]]

    def _rerank_api(self, query: str, doc_ids: List[str], k: int) -> List[str]:
        """Rerank via an OpenAI-compatible rerank endpoint (e.g. SiliconFlow /v1/rerank)."""
        if not self.rerank_api_key:
            print("[retriever] rerank API key missing; rerank disabled.")
            return doc_ids
        import requests

        documents = [self.by_id[did]["text"][:512] for did in doc_ids]
        resp = requests.post(
            f"{self.rerank_base_url.rstrip('/')}/rerank",
            headers={"Authorization": f"Bearer {self.rerank_api_key}"},
            json={"model": self.rerank_model, "query": query, "documents": documents, "top_n": k},
            timeout=30,
        )
        resp.raise_for_status()
        ranked = sorted(resp.json().get("results", []), key=lambda r: r["relevance_score"], reverse=True)
        return [doc_ids[r["index"]] for r in ranked[:k]]

    def contexts(self, doc_ids: List[str]) -> List[dict]:
        return [self.by_id[did] for did in doc_ids if did in self.by_id]
