"""
retriever.py — TaxRetriever: hybrid FAISS (dense) + BM25 (sparse) retrieval with RRF.

Loaded once at startup and stored on app.state.retriever. If the index files
are missing it raises FileNotFoundError and chat returns 503.

  - Dense:  FAISS IndexFlatIP over L2-normalised embeddings (cosine)
  - Sparse: BM25Okapi over regex tokens (so "80C," and "80C" match)
  - Fusion: Reciprocal Rank Fusion, score = Σ 1/(k + rank), k = 60, rank 1-indexed

The query embedder must match the one recorded in meta.json at build time.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Literal, Optional

import faiss
import numpy as np
from rank_bm25 import BM25Okapi

from backend.agents.matcher_agent.embeddings import Embedder, make_embedder

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_INDEX_DIR = PROJECT_ROOT / "knowledge_base" / "indexes"
RRF_K = 60

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    "a an the of to in on for and or is are was were be by with as at from that this it "
    "its i my me can do does how what which who when under than".split()
)

Mode = Literal["hybrid", "dense", "sparse"]


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS]


class TaxRetriever:
    def __init__(self, index_dir: Path = DEFAULT_INDEX_DIR, embedder: Optional[Embedder] = None) -> None:
        faiss_path = index_dir / "kb.faiss"
        chunks_path = index_dir / "chunks.json"
        meta_path = index_dir / "meta.json"
        for p in (faiss_path, chunks_path, meta_path):
            if not p.exists():
                raise FileNotFoundError(
                    f"{p} not found. Build it with: python -m backend.agents.matcher_agent.build_index"
                )

        self.index = faiss.read_index(str(faiss_path))
        self.chunks: list[dict] = json.loads(chunks_path.read_text(encoding="utf-8"))
        self.meta: dict = json.loads(meta_path.read_text(encoding="utf-8"))
        self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])

        if embedder is None:
            prefix = self.meta.get("embedder", "").split(":", 1)[0]
            kind = "bge-m3" if prefix == "local" else "gemini"
            embedder = make_embedder(kind)
        self.embedder = embedder
        logger.info(
            "TaxRetriever ready: %d chunks, dim=%d, embedder=%s (index built with %s)",
            len(self.chunks), self.index.d, embedder.name, self.meta.get("embedder"),
        )

    # ── individual retrievers ────────────────────────────────────────────────
    def dense_search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        vec = np.asarray(self.embedder.embed_query(query), dtype=np.float32).reshape(1, -1)
        scores, indices = self.index.search(vec, top_k)
        return [(int(i), float(s)) for i, s in zip(indices[0], scores[0]) if i >= 0]

    def sparse_search(self, query: str, top_k: int = 20) -> list[tuple[int, float]]:
        scores = self.bm25.get_scores(tokenize(query))
        top = np.argsort(scores)[::-1][:top_k]
        return [(int(i), float(scores[i])) for i in top if scores[i] > 0]

    # ── public API ──────────────────────────────────────────────────────────
    def search(self, query: str, top_k: int = 10, mode: Mode = "hybrid") -> list[dict]:
        if mode == "dense":
            return [self.chunks[i] for i, _ in self.dense_search(query, top_k)]
        if mode == "sparse":
            return [self.chunks[i] for i, _ in self.sparse_search(query, top_k)]
        return self.hybrid_search(query, top_k)

    def hybrid_search(self, query: str, top_k: int = 10) -> list[dict]:
        """Reciprocal Rank Fusion of dense + sparse top-20 lists."""
        fused: dict[str, float] = {}
        by_id: dict[str, dict] = {}
        for results in (self.dense_search(query, 20), self.sparse_search(query, 20)):
            for rank, (idx, _score) in enumerate(results, start=1):
                chunk = self.chunks[idx]
                cid = chunk["chunk_id"]
                fused[cid] = fused.get(cid, 0.0) + 1.0 / (RRF_K + rank)
                by_id[cid] = chunk
        ordered = sorted(fused, key=lambda cid: (-fused[cid], cid))
        return [by_id[cid] for cid in ordered[:top_k]]
