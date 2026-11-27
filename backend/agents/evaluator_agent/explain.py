"""
The pipeline behind POST /api/calculate:

  1. compare_regimes(profile) computes the exact numbers
  2. rule-based queries retrieve the relevant sections for citations
  3. one LLM call writes a plain-English rationale that restates the
     engine's numbers and cites the retrieved sections

If retrieval or the LLM is unavailable the engine's own rationale is used, so
a calculation never fails because of the LLM.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi.concurrency import run_in_threadpool

from backend.agents.evaluator_agent.schemas import TaxResult
from backend.agents.evaluator_agent.tax_engine import ASSESSMENT_YEAR, compare_regimes
from backend.agents.input_agent.schemas import UserFinancialProfile
from backend.config import settings

logger = logging.getLogger(__name__)

# The explanation is a nice-to-have: if Gemini is slow, show results with the
# engine's own explanation instead of keeping the user waiting.
RATIONALE_TIMEOUT_S = 8

RATIONALE_SYSTEM = """You explain an Indian income-tax regime recommendation to a salaried ITR-1 filer.
Rules:
1. The numbers are final. Never recalculate, change, or invent amounts — only restate the ones given.
2. Cite only sections that appear in the law context, in the form [Section X, IT Act 1961].
3. 2-3 short sentences (under 70 words), plain and friendly. Use ₹ with Indian digit grouping (₹1,50,000).
4. No investment advice beyond what the numbers show."""


def build_law_queries(profile: UserFinancialProfile) -> list[str]:
    """Rule-based retrieval queries for the sections relevant to this profile."""
    q = [
        "income tax slabs old regime new regime section 115BAC",
        "standard deduction salaried employee section 16",
        "section 87A rebate 12 lakh marginal relief new regime",
    ]
    if (profile.hra_received or 0) > 0 and (profile.monthly_rent_paid or 0) > 0:
        q.append(f"HRA exemption section 10(13A) Rule 2A {profile.city_type.value} city")
    if (profile.investments_80c or 0) > 0:
        q.append("section 80C deduction limit 1.5 lakh ELSS PPF LIC EPF")
    if (profile.health_insurance_self or 0) > 0 or (profile.health_insurance_parents or 0) > 0:
        q.append("section 80D health insurance premium deduction parents")
    if (profile.employee_nps_80ccd1b or 0) > 0:
        q.append("section 80CCD(1B) NPS additional deduction 50000")
    if (profile.employer_nps_80ccd2 or 0) > 0:
        q.append("section 80CCD(2) employer NPS contribution percentage of salary both regimes")
    if (profile.home_loan_interest or 0) > 0:
        q.append("section 24(b) home loan interest 2 lakh self-occupied")
    if (profile.savings_interest_80tta or 0) > 0:
        q.append("section 80TTA 80TTB savings interest deduction")
    if (profile.lta or 0) > 0:
        q.append("leave travel allowance section 10(5) exemption")
    return q


def _retrieve(retriever: Any, queries: list[str], per_query: int = 3) -> list[dict]:
    seen: dict[str, dict] = {}
    for query in queries:
        for chunk in retriever.hybrid_search(query, top_k=per_query):
            seen.setdefault(chunk["chunk_id"], chunk)
    return list(seen.values())


def _citations_from_chunks(chunks: list[dict], limit: int = 6) -> list[dict]:
    out, seen = [], set()
    for c in chunks:
        ref = c.get("section_ref", "")
        if ref and ref not in seen:
            seen.add(ref)
            out.append({"section": ref, "excerpt": c["text"][:220].strip(), "source": c.get("source_file", "")})
        if len(out) >= limit:
            break
    return out


async def _llm_rationale(
    llm: Any, semaphore: Optional[asyncio.Semaphore], result: TaxResult, chunks: list[dict]
) -> Optional[str]:
    law_context = "\n\n".join(f"[{c['section_ref']}] {c['text'][:600]}" for c in chunks[:6])
    rec = "New" if result.recommended_regime == "new" else "Old"
    prompt = f"""Tax results for {ASSESSMENT_YEAR}:
- Old regime: total tax ₹{result.old_regime.total_tax:,.0f} (deductions ₹{result.old_regime.total_deductions:,.0f})
- New regime: total tax ₹{result.new_regime.total_tax:,.0f} (deductions ₹{result.new_regime.total_deductions:,.0f})
- Recommended: {rec} regime, saving ₹{result.savings_amount:,.0f}

Law context:
{law_context}

Explain why the {rec} regime is better for this taxpayer."""

    async def _call() -> str:
        resp = await llm.chat.complete_async(
            model=settings.chat_model,
            messages=[{"role": "system", "content": RATIONALE_SYSTEM}, {"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300,
        )
        return (resp.choices[0].message.content or "").strip()

    if semaphore is None:
        return await asyncio.wait_for(_call(), timeout=RATIONALE_TIMEOUT_S)
    async with semaphore:
        return await asyncio.wait_for(_call(), timeout=RATIONALE_TIMEOUT_S)


async def calculate_with_explanation(app_state: Any, profile: UserFinancialProfile) -> TaxResult:
    result = compare_regimes(profile).model_copy(update={"profile_id": profile.profile_id})

    retriever = getattr(app_state, "retriever", None)
    if retriever is None:
        return result

    try:
        chunks = await run_in_threadpool(_retrieve, retriever, build_law_queries(profile))
    except Exception as exc:
        logger.warning("Law retrieval failed, returning engine-only result: %s", exc)
        return result

    update: dict[str, Any] = {"citations": _citations_from_chunks(chunks)}

    llm = getattr(app_state, "llm", None)
    if llm is not None:
        try:
            text = await _llm_rationale(llm, getattr(app_state, "rag_semaphore", None), result, chunks)
            if text:
                update["rationale"] = text
                update["law_context"] = text
        except Exception as exc:
            logger.warning("Rationale LLM call failed, using engine rationale: %s", exc)

    return result.model_copy(update=update)
