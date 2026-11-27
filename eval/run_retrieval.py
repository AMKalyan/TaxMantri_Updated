"""
Retrieval evaluation: BM25-only vs FAISS-only vs hybrid (RRF).

Gold labels are at the source-file (section) level, so re-chunking does not
invalidate them. A retrieved chunk is relevant if its source_file is in the
question's `relevant` list.

Metrics (per mode, averaged over questions):
  hit@k     — at least one relevant chunk in the top k
  recall@k  — fraction of the question's relevant files covered by the top k
  MRR       — 1 / rank of the first relevant chunk (0 if none in top 20)

Usage (repository root):
  python -m eval.run_retrieval                                  # production index (gemini-embedding-001)
  python -m eval.run_retrieval --index knowledge_base/indexes_bge  # bge-m3 baseline index
  python -m eval.run_retrieval --bm25-only                      # no API key / index needed

Writes eval/results/<date>-retrieval[-<tag>].md and .json.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "eval" / "data" / "tax_questions.jsonl"
RESULTS = ROOT / "eval" / "results"
KS = (1, 3, 5, 10)
MAX_K = 20


def load_questions() -> list[dict]:
    return [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]


def score(ranked_files: list[str], relevant: set[str]) -> dict:
    out = {}
    for k in KS:
        top = ranked_files[:k]
        out[f"hit@{k}"] = 1.0 if any(f in relevant for f in top) else 0.0
        out[f"recall@{k}"] = len(relevant & set(top)) / len(relevant)
    rr = 0.0
    for i, f in enumerate(ranked_files[:MAX_K], start=1):
        if f in relevant:
            rr = 1.0 / i
            break
    out["mrr"] = rr
    return out


def average(rows: list[dict]) -> dict:
    keys = rows[0].keys()
    return {k: round(sum(r[k] for r in rows) / len(rows), 4) for k in keys}


def git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def run(index_dir: Path | None, bm25_only: bool, tag: str) -> dict:
    from backend.agents.matcher_agent.retriever import TaxRetriever

    questions = load_questions()
    if bm25_only:
        from rank_bm25 import BM25Okapi

        from backend.agents.matcher_agent.build_index import load_chunks
        from backend.agents.matcher_agent.retriever import tokenize

        class _Bm25Only:
            def __init__(self):
                self.chunks = load_chunks()
                self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])
                self.meta = {"embedder": "none"}
            sparse_search = TaxRetriever.sparse_search
            def search(self, q, top_k, mode):
                return [self.chunks[i] for i, _ in self.sparse_search(q, top_k)]

        retriever = _Bm25Only()
        modes = ["sparse"]
    else:
        retriever = TaxRetriever(index_dir) if index_dir else TaxRetriever()
        modes = ["sparse", "dense", "hybrid"]

    per_mode: dict[str, dict] = {}
    per_question: dict[str, dict] = {}
    for mode in modes:
        rows = []
        for q in questions:
            chunks = retriever.search(q["question"], top_k=MAX_K, mode=mode)
            files = [c["source_file"] for c in chunks]
            s = score(files, set(q["relevant"]))
            rows.append(s)
            per_question.setdefault(q["id"], {})[mode] = {"mrr": s["mrr"], "top3": files[:3]}
        per_mode[mode] = {
            "all": average(rows),
            "lay": average([r for r, q in zip(rows, questions) if q["style"] == "lay"]),
            "statute": average([r for r, q in zip(rows, questions) if q["style"] == "statute"]),
        }

    meta = getattr(retriever, "meta", {})
    report = {
        "date": dt.date.today().isoformat(),
        "commit": git_commit(),
        "embedder": meta.get("embedder"),
        "chunk_words": meta.get("chunk_words"),
        "overlap_words": meta.get("overlap_words"),
        "chunks": len(retriever.chunks),
        "questions": len(questions),
        "ks": list(KS),
        "rrf_k": 60,
        "results": per_mode,
        "per_question": per_question,
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = f"{report['date']}-retrieval" + (f"-{tag}" if tag else "")
    (RESULTS / f"{stem}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    names = {"sparse": "BM25 only", "dense": "FAISS only", "hybrid": "Hybrid (RRF)"}
    lines = [
        f"# Retrieval eval — {report['date']}",
        "",
        f"- Commit `{report['commit']}`, embedder `{report['embedder']}`, {report['chunks']} chunks "
        f"({report['chunk_words']} words, overlap {report['overlap_words']}), {report['questions']} questions, RRF k=60",
        "",
    ]
    for subset in ("all", "lay", "statute"):
        lines += [f"## {subset.capitalize()} questions", "",
                  "| Mode | hit@1 | hit@3 | hit@5 | recall@5 | recall@10 | MRR |",
                  "|---|---|---|---|---|---|---|"]
        for mode in modes:
            m = per_mode[mode][subset]
            lines.append(f"| {names[mode]} | {m['hit@1']:.2f} | {m['hit@3']:.2f} | {m['hit@5']:.2f} | "
                         f"{m['recall@5']:.2f} | {m['recall@10']:.2f} | {m['mrr']:.3f} |")
        lines.append("")
    (RESULTS / f"{stem}.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--index", type=Path, default=None)
    p.add_argument("--bm25-only", action="store_true")
    p.add_argument("--tag", default="")
    a = p.parse_args()
    run(a.index, a.bm25_only, a.tag)
