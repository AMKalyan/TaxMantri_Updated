"""
embeddings.py — text embedders for the knowledge-base index.

Production uses GeminiEmbedder (an API call, so no model is loaded and the server
fits in 512 MB). LocalEmbedder (BAAI/bge-m3) exists only as an offline comparison
for the retrieval eval; it needs `pip install sentence-transformers`.

Both return L2-normalised float32 vectors, so FAISS inner product equals cosine similarity.
"""
from __future__ import annotations

import logging
import time
from functools import lru_cache
from typing import Protocol

import numpy as np

logger = logging.getLogger(__name__)


def _normalise(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...


class GeminiEmbedder:
    """Embeddings from Gemini (`gemini-embedding-001`, 3072 dimensions)."""

    def __init__(self, api_key: str, model: str = "gemini-embedding-001", batch_size: int = 50) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required to embed text")
        from openai import OpenAI

        from backend.llm import GEMINI_OPENAI_BASE_URL

        self._client = OpenAI(api_key=api_key, base_url=GEMINI_OPENAI_BASE_URL, timeout=30, max_retries=0)
        self.model = model
        self.name = f"gemini:{model}"
        self.batch_size = batch_size
        # Repeated questions skip the API round-trip.
        self.embed_query = lru_cache(maxsize=1024)(self._embed_query_uncached)  # type: ignore[method-assign]

    def _call(self, inputs: list[str]) -> list[list[float]]:
        for attempt in range(5):
            try:
                resp = self._client.embeddings.create(model=self.model, input=inputs)
                return [d.embedding for d in resp.data]
            except Exception as exc:  # free-tier rate limits are tight, so back off and retry
                if attempt == 4:
                    raise
                wait = 3 * 2 ** attempt
                logger.warning("Gemini embeddings failed (%s); retrying in %ss", str(exc)[:120], wait)
                time.sleep(wait)
        raise RuntimeError("unreachable")

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._call(texts[i : i + self.batch_size]))
        return _normalise(np.array(out))

    def _embed_query_uncached(self, text: str) -> np.ndarray:
        return _normalise(np.array(self._call([text])))


class LocalEmbedder:
    """BAAI/bge-m3 via sentence-transformers — offline eval baseline only."""

    def __init__(self, model: str = "BAAI/bge-m3") -> None:
        from sentence_transformers import SentenceTransformer  # optional dependency

        self._model = SentenceTransformer(model)
        self.name = f"local:{model}"

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _normalise(self._model.encode(texts, batch_size=16, show_progress_bar=True))

    def embed_query(self, text: str) -> np.ndarray:
        return _normalise(self._model.encode([text], show_progress_bar=False))


def make_embedder(kind: str = "gemini") -> Embedder:
    """'gemini' (production) or 'bge-m3' (local baseline)."""
    if kind in ("bge-m3", "local"):
        return LocalEmbedder()
    from backend.config import settings

    return GeminiEmbedder(settings.gemini_api_key, model=settings.gemini_embed_model)
