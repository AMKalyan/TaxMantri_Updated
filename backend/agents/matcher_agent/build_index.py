"""
build_index.py — offline knowledge-base indexing.

Reads knowledge_base/raw/*.txt, splits them into overlapping word-window chunks,
embeds them, and writes:
    <out>/kb.faiss     FAISS IndexFlatIP (cosine on L2-normalised vectors)
    <out>/chunks.json  chunk metadata + text (used for BM25 and citations)
    <out>/meta.json    embedder name, dimension, chunking params, AY

Run from the repository root (needs GEMINI_API_KEY):
    python -m backend.agents.matcher_agent.build_index
    python -m backend.agents.matcher_agent.build_index --embedder bge-m3 --out knowledge_base/indexes_bge

The production index is built offline, committed and shipped in the Docker
image; the server doesn't rebuild it at startup.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import faiss
import numpy as np

log = logging.getLogger(__name__)

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent.parent.parent
RAW_DIR: Path = PROJECT_ROOT / "knowledge_base" / "raw"
INDEX_DIR: Path = PROJECT_ROOT / "knowledge_base" / "indexes"

# ~500 tokens ≈ 350 English words; overlap ≈ 50 tokens.
CHUNK_WORDS = 350
OVERLAP_WORDS = 40

ASSESSMENT_YEAR = "AY2026-27"

FILE_CATALOGUE: dict[str, str] = {
    "section_15": "IT Act S.15",
    "section_16": "IT Act S.16",
    "section_10_13a": "IT Act S.10(13A)",
    "section_10_5": "IT Act S.10(5)",
    "section_10_10d": "IT Act S.10(10D)",
    "section_24": "IT Act S.24",
    "section_80c": "IT Act S.80C",
    "section_80d": "IT Act S.80D",
    "section_80ccd": "IT Act S.80CCD",
    "section_80e": "IT Act S.80E",
    "section_80g": "IT Act S.80G",
    "section_80tta": "IT Act S.80TTA",
    "section_87a": "IT Act S.87A",
    "section_89a": "IT Act S.89A",
    "section_115bac": "IT Act S.115BAC",
    "hra_rule_2a": "IT Rules Rule 2A",
    "budget_2025_amendments": "Budget 2025",
    "itr1_instructions": "ITR-1 Instructions",
    "form16_guide": "Form 16 Guide",
}


def chunk_text(text: str, size: int = CHUNK_WORDS, overlap: int = OVERLAP_WORDS) -> list[str]:
    """Split text into overlapping windows of `size` words."""
    words = text.split()
    if not words:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += size - overlap
    return chunks


def load_chunks(raw_dir: Path = RAW_DIR) -> list[dict[str, Any]]:
    missing = [s for s in FILE_CATALOGUE if not (raw_dir / f"{s}.txt").exists()]
    if missing:
        log.error("Missing knowledge-base files in %s: %s", raw_dir, missing)
        sys.exit(1)
    all_chunks: list[dict[str, Any]] = []
    for stem, section_ref in FILE_CATALOGUE.items():
        raw_text = (raw_dir / f"{stem}.txt").read_text(encoding="utf-8")
        for idx, text in enumerate(chunk_text(raw_text)):
            all_chunks.append(
                {
                    "chunk_id": f"{stem}_chunk_{idx:03d}",
                    "source_file": f"{stem}.txt",
                    "section_ref": section_ref,
                    "assessment_year": ASSESSMENT_YEAR,
                    "chunk_index": idx,
                    "text": text,
                }
            )
    return all_chunks


def main(embedder_kind: str = "gemini", out_dir: Path = INDEX_DIR, raw_dir: Path = RAW_DIR) -> None:
    from backend.agents.matcher_agent.embeddings import make_embedder

    out_dir.mkdir(parents=True, exist_ok=True)
    chunks = load_chunks(raw_dir)
    log.info("Loaded %d chunks from %d files", len(chunks), len(FILE_CATALOGUE))

    embedder = make_embedder(embedder_kind)
    log.info("Embedding with %s ...", embedder.name)
    vectors = embedder.embed_documents([c["text"] for c in chunks]).astype(np.float32)

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    faiss.write_index(index, str(out_dir / "kb.faiss"))
    (out_dir / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "embedder": embedder.name,
                "dim": int(vectors.shape[1]),
                "chunks": len(chunks),
                "chunk_words": CHUNK_WORDS,
                "overlap_words": OVERLAP_WORDS,
                "assessment_year": ASSESSMENT_YEAR,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("Index written to %s (%d vectors, dim=%d)", out_dir, index.ntotal, vectors.shape[1])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(description="Build the TaxMantri RAG index")
    p.add_argument("--embedder", default="gemini", choices=["gemini", "bge-m3"])
    p.add_argument("--out", type=Path, default=INDEX_DIR)
    args = p.parse_args()
    main(args.embedder, args.out)
