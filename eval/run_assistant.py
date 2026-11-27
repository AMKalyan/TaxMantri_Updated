"""
Live assistant eval: runs the real agent (configured LLM provider) on scenario
questions and checks the answers against the deterministic engine and the law.

A case passes when every `must_include` figure/phrase is in the answer and no
`must_not_include` phrase is. Figures are computed by the engine at run time.

Usage:  python -m eval.run_assistant          (needs the built index + API key)
Writes eval/results/<date>-assistant.md/.json
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
import subprocess
import time
from pathlib import Path

from backend.agents.assistant.agent import run_agent
from backend.agents.evaluator_agent.fmt import inr
from backend.agents.evaluator_agent.tax_engine import compare_regimes
from backend.agents.input_agent.schemas import UserFinancialProfile
from backend.agents.matcher_agent.retriever import TaxRetriever
from backend.config import settings
from backend.llm import make_llm_client

ROOT = Path(__file__).resolve().parent.parent
MAX_WORDS = 110   # target is 80-100 words; small slack for rupee figures and citations
RESULTS = ROOT / "eval" / "results"

SAVED = UserFinancialProfile(
    input_method="manual", basic_salary=900_000, hra_received=360_000, special_allowance=300_000,
    monthly_rent_paid=25_000, city_type="metro", age_bracket="under60",
    investments_80c=150_000, health_insurance_self=25_000,
)


def _tax(profile: UserFinancialProfile, regime: str) -> str:
    r = compare_regimes(profile)
    return inr((r.old_regime if regime == "old" else r.new_regime).total_tax)


def cases() -> list[dict]:
    with_nps = SAVED.model_copy(update={"employee_nps_80ccd1b": 50_000})
    p14 = UserFinancialProfile(input_method="manual", basic_salary=1_400_000, city_type="metro", age_bracket="under60")
    p1275 = UserFinancialProfile(input_method="manual", basic_salary=1_275_000, city_type="metro", age_bracket="under60")
    return [
        {"id": "whatif_nps", "profile": SAVED,
         "q": "Which regime is better for me, and what if I put 50,000 into NPS under 80CCD(1B)?",
         "must_include": [_tax(SAVED, "old"), _tax(SAVED, "new"), _tax(with_nps, "old")]},
        {"id": "my_current_tax", "profile": SAVED, "q": "How much tax do I pay in each regime?",
         "must_include": [_tax(SAVED, "old"), _tax(SAVED, "new")]},
        {"id": "hypothetical_14L", "profile": None,
         "q": "I earn 14 lakh salary, nothing else. How much tax in the new regime?",
         "must_include": [_tax(p14, "new")]},
        {"id": "zero_tax_1275", "profile": None,
         "q": "Is a salary of 12.75 lakh tax-free under the new regime?",
         "must_include": ["tax-free", "87a"]},
        {"id": "itr1_two_houses", "profile": None, "q": "Can I file ITR-1 if I own two houses?",
         "must_include": ["yes", "two"], "must_not_include": ["only one house", "cannot file itr-1"]},
        {"id": "80c_limit", "profile": None, "q": "What is the maximum deduction under section 80C?",
         "must_include": ["1,50,000"]},
        {"id": "marginal_relief", "profile": None,
         "q": "My taxable income is 12.1 lakh in the new regime. Do I lose the whole rebate?",
         "must_include": ["marginal relief"]},
    ]


def _normalise_amounts(text: str) -> str:
    """Rewrite any rupee amount into Indian grouping so ₹1,56,000 and ₹156,000 compare equal."""
    def fix(m: re.Match) -> str:
        return inr(float(m.group(0).replace(",", "")))
    return re.sub(r"\d{1,3}(?:,\d{2,3})+|\d{4,}", fix, text)


async def main() -> None:
    llm = make_llm_client()
    if llm is None:
        raise SystemExit("Set GEMINI_API_KEY first")
    retriever = TaxRetriever()
    rows = []
    for c in cases():
        t = time.time()
        for attempt in range(2):   # one retry on transient free-tier timeouts
            try:
                out = await run_agent(llm.chat.complete_async, settings.chat_model, c["q"], retriever, c["profile"])
                answer = out["answer"]
                break
            except Exception as exc:
                out, answer = {"steps": [], "grounded": False}, f"ERROR: {exc}"
        norm = _normalise_amounts(answer).lower()
        missing = [m for m in c["must_include"] if m.lower() not in norm]
        words = len(answer.split())
        if words > MAX_WORDS:
            missing.append(f"too long ({words} words)")
        if re.search(r"^\s*(#|[-*] |\d+\. |\|)|\*\*", answer, re.M):
            missing.append("uses headings or lists")
        forbidden = [m for m in c.get("must_not_include", []) if m.lower() in norm]
        rows.append({
            "id": c["id"], "question": c["q"], "passed": not missing and not forbidden,
            "missing": missing, "forbidden": forbidden, "seconds": round(time.time() - t, 1),
            "tools": [s["tool"] for s in out["steps"]], "grounded": out.get("grounded"), "words": len(answer.split()), "answer": answer,
        })
        print(f"{'PASS' if rows[-1]['passed'] else 'FAIL'}  {c['id']:18} {rows[-1]['seconds']:5.1f}s "
              f"tools={rows[-1]['tools']} missing={missing} forbidden={forbidden}")

    passed = sum(r["passed"] for r in rows)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "unknown"
    report = {"date": dt.date.today().isoformat(), "commit": commit, "provider": "gemini",
              "model": settings.chat_model, "passed": passed, "total": len(rows), "cases": rows}
    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = f"{report['date']}-assistant-{settings.chat_model}"
    (RESULTS / f"{stem}.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = [f"# Assistant eval — {report['date']}", "",
             f"- Commit `{commit}`, Gemini `{settings.chat_model}` — **{passed}/{len(rows)} passed**", "",
             "| Case | Result | Tools | Time | Missing / forbidden |", "|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['id']} | {'pass' if r['passed'] else 'FAIL'} | {', '.join(r['tools']) or '—'} | "
                     f"{r['seconds']}s | {', '.join(r['missing'] + r['forbidden']) or '—'} |")
    (RESULTS / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(rows)} passed")


if __name__ == "__main__":
    asyncio.run(main())
