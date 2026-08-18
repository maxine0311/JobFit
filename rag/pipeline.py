"""End-to-end RAG pipeline: ask() with latency, tokens and cost."""

from __future__ import annotations

import os
import time

from rag.config import Settings, settings as default_settings
from rag.generator import Generator
from rag.retriever import Retriever
from rag.vector_store import VectorStore


class RagPipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or default_settings
        self.vector_store = VectorStore(self.settings.chroma_dir)
        if not os.path.exists(self.settings.chunks_json):
            raise FileNotFoundError(
                f"{self.settings.chunks_json} not found. Run `python scripts/ingest.py` first."
            )
        self.retriever = Retriever(
            chunks_json=self.settings.chunks_json,
            vector_store=self.vector_store,
            rerank_provider=self.settings.rerank_provider,
            rerank_model=self.settings.rerank_model,
            rerank_api_key=self.settings.rerank_api_key,
            rerank_base_url=self.settings.rerank_base_url,
        )
        self.generator = Generator(self.settings)

    def embed(self, texts: list[str]) -> list[list[float]]:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.embedding_api_key, base_url=self.settings.embedding_base_url)
        resp = client.embeddings.create(model=self.settings.embedding_model, input=texts)
        return [item.embedding for item in resp.data]

    def ask(
        self,
        question: str,
        k: int | None = None,
        hybrid: bool = True,
        rerank: bool = False,
        temperature: float = 0.0,
    ) -> dict:
        k = k or self.settings.top_k
        t0 = time.perf_counter()
        query_embedding = self.embed([question])[0]

        if hybrid:
            doc_ids = self.retriever.hybrid_topk(question, query_embedding, k=k)
        else:
            doc_ids = self.retriever.dense_topk(query_embedding, k=k)
        if rerank:
            doc_ids = self.retriever.rerank(question, doc_ids, k=k)

        contexts = self.retriever.contexts(doc_ids)
        out = self.generator.answer(question, contexts, temperature=temperature)
        latency_s = time.perf_counter() - t0
        return {
            "question": question,
            "answer": out["answer"],
            "sources": [
                {
                    "id": c["id"],
                    "source": c["source"],
                    "snippet": c["text"][:200],
                    "company": c.get("company", ""),
                    "position": c.get("position", ""),
                    "link": c.get("link", ""),
                }
                for c in contexts
            ],
            "latency_s": round(latency_s, 2),
            "prompt_tokens": out["prompt_tokens"],
            "completion_tokens": out["completion_tokens"],
            "cost_usd": round(self.generator.cost_usd(out["prompt_tokens"], out["completion_tokens"]), 5),
        }
