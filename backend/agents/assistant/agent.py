"""
agent.py — TaxMantri's tool-using tax assistant.

Gemini decides which tools to call, reads the results and then answers. All
figures come from the deterministic tax engine; the model only plans and
explains, it never computes tax itself.

Tools
  search_tax_law(query)            hybrid retrieval over the IT Act knowledge base
  calculate_tax(profile)           exact Old vs New regime comparison
  what_if(changes, base_profile?)  re-run the engine with changes applied
  get_my_profile()                 the user's saved profile (only if a profile_id is in scope)

Guardrails
  - at most MAX_TOOL_CALLS tool calls per question, after which the model has
    to answer
  - every ₹ amount in the answer has to appear in a tool result or retrieved
    law text; if not, the model gets one retry, and a second failure returns
    the answer with `grounded = False`
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from backend.agents.evaluator_agent.tax_engine import ASSESSMENT_YEAR, compare_regimes
from backend.agents.input_agent.schemas import UserFinancialProfile

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS = 4
TOOL_RESULT_CHAR_LIMIT = 9000

SYSTEM_PROMPT = f"""You are TaxMantri, an assistant for Indian salaried taxpayers filing ITR-1 for {ASSESSMENT_YEAR} (FY 2025-26) under the Income-tax Act, 1961.

You have tools. Use them:
- search_tax_law for rules, limits, eligibility and definitions. Cite what you use as [Section X, IT Act 1961].
- For the user's OWN saved profile, use what_if: changes={{}} gives their current tax, and other changes give scenarios.
  Do not rebuild their profile by hand for calculate_tax — you would drop fields like HRA and rent.
- calculate_tax only for a hypothetical salary the user describes in the conversation.
- Never do tax arithmetic yourself.

The search results reflect the law for {ASSESSMENT_YEAR}, including recent changes that may be newer than
what you remember. When they answer the question, follow them over your own memory.

Rules:
1. Every ₹ amount you state must come from a tool result. If you have no tool result for a number, don't state it.
2. If information is missing (e.g. salary), ask for it instead of guessing.
3. Keep it short and precise: at most 80-100 words. Lead with the direct answer, then only the key ₹ figures
   (Indian digit grouping, e.g. ₹1,50,000) and one or two citations. Say which regime is better when you compared.
4. Plain sentences only: no headings, bullet lists, tables or bold — even for comparisons.
5. Mention consulting a CA only for genuinely complex situations, not on every answer."""

_PROFILE_PROPS = {
    "basic_salary": {"type": "number", "description": "Annual basic salary (or total gross salary if no breakup)"},
    "hra_received": {"type": "number", "description": "Annual HRA received"},
    "special_allowance": {"type": "number"},
    "other_allowances": {"type": "number"},
    "lta": {"type": "number"},
    "monthly_rent_paid": {"type": "number", "description": "Monthly rent"},
    "city_type": {"type": "string", "enum": ["metro", "non_metro"]},
    "age_bracket": {"type": "string", "enum": ["under60", "60_79", "80plus"]},
    "other_income": {"type": "number"},
    "investments_80c": {"type": "number"},
    "health_insurance_self": {"type": "number"},
    "health_insurance_parents": {"type": "number"},
    "parent_senior_citizen": {"type": "boolean"},
    "employee_nps_80ccd1b": {"type": "number"},
    "employer_nps_80ccd2": {"type": "number"},
    "home_loan_interest": {"type": "number"},
    "savings_interest_80tta": {"type": "number"},
    "professional_tax": {"type": "number"},
}

TOOLS = [
    {"type": "function", "function": {
        "name": "search_tax_law",
        "description": "Search the Income-tax Act knowledge base (sections, limits, eligibility, ITR-1 rules).",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "calculate_tax",
        "description": "Exact Old vs New regime tax for a HYPOTHETICAL salary profile described in the chat (annual INR, except monthly_rent_paid). For the user's saved profile use what_if instead.",
        "parameters": {"type": "object", "properties": _PROFILE_PROPS, "required": ["basic_salary"]},
    }},
    {"type": "function", "function": {
        "name": "what_if",
        "description": "Tax for the user's saved profile, before and after applying changes (e.g. {\"employee_nps_80ccd1b\": 50000}). Use changes={} to get their current tax. base_profile overrides the saved profile. Returns before, after and the difference.",
        "parameters": {"type": "object", "properties": {
            "changes": {"type": "object", "properties": _PROFILE_PROPS},
            "base_profile": {"type": "object", "properties": _PROFILE_PROPS},
        }, "required": ["changes"]},
    }},
    {"type": "function", "function": {
        "name": "get_my_profile",
        "description": "Return the user's saved salary/deduction profile, if they have calculated their tax in this session.",
        "parameters": {"type": "object", "properties": {}},
    }},
]

TARGET_WORDS = 90          # answers aim for 80-100 words
_MARKDOWN_RE = re.compile(r"^\s*(#{1,6} |[-*•] |\d+\. |\|)|\*\*", re.M)


def _too_long_or_formatted(answer: str) -> bool:
    return len(answer.split()) > 100 or bool(_MARKDOWN_RE.search(answer))


_RUPEE_RE = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:rupees|/-)", re.IGNORECASE
)
_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


@dataclass
class AgentContext:
    retriever: Any
    profile: Optional[UserFinancialProfile] = None
    chunks_seen: list[dict] = field(default_factory=list)
    tool_texts: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)


# ── tool implementations ──────────────────────────────────────────────────────
def _summarise(profile: UserFinancialProfile) -> dict:
    r = compare_regimes(profile)
    def regime(x):
        return {
            "gross_income": round(x.gross_income), "total_deductions": round(x.total_deductions),
            "taxable_income": round(x.taxable_income), "total_tax": round(x.total_tax),
        }
    return {
        "assessment_year": ASSESSMENT_YEAR,
        "old_regime": regime(r.old_regime), "new_regime": regime(r.new_regime),
        "recommended_regime": r.recommended_regime, "savings_with_recommended": round(r.savings_amount),
        "old_regime_tips": r.old_regime_suggestions[:3], "new_regime_tips": r.new_regime_suggestions[:3],
    }


def _build_profile(data: dict) -> UserFinancialProfile:
    clean = {k: v for k, v in (data or {}).items() if k in _PROFILE_PROPS and v is not None}
    clean.setdefault("city_type", "metro")
    clean.setdefault("age_bracket", "under60")
    return UserFinancialProfile(input_method="manual", **clean)


def _tool_search(ctx: AgentContext, args: dict) -> dict:
    if ctx.retriever is None:
        return {"error": "Tax-law search is unavailable right now."}
    chunks = ctx.retriever.hybrid_search(str(args.get("query", ""))[:300], top_k=3)
    ctx.chunks_seen.extend(chunks)
    return {"results": [{"section": c["section_ref"], "source": c["source_file"], "text": c["text"][:2800]} for c in chunks]}


def _tool_calculate(ctx: AgentContext, args: dict) -> dict:
    profile = _build_profile(args)
    return _summarise(profile)


def _tool_what_if(ctx: AgentContext, args: dict) -> dict:
    base = _build_profile(args["base_profile"]) if args.get("base_profile") else ctx.profile
    if base is None:
        return {"error": "No saved profile. Ask the user for their salary details or call calculate_tax first."}
    changes = {k: v for k, v in (args.get("changes") or {}).items() if k in _PROFILE_PROPS}
    after_profile = base.model_copy(update=changes)
    after_profile = UserFinancialProfile.model_validate(after_profile.model_dump())  # re-validate
    before, after = _summarise(base), _summarise(after_profile)
    delta = {
        r: after[f"{r}_regime"]["total_tax"] - before[f"{r}_regime"]["total_tax"] for r in ("old", "new")
    }
    return {"changes": changes, "before": before, "after": after, "tax_change": delta}


def _tool_profile(ctx: AgentContext, args: dict) -> dict:
    if ctx.profile is None:
        return {"error": "The user has not calculated their tax yet in this session."}
    data = ctx.profile.model_dump(exclude={"profile_id", "input_method", "hra_exemption_declared", "lta_exemption_declared"})
    return {k: (v.value if hasattr(v, "value") else v) for k, v in data.items() if v not in (None, 0, False)}


TOOL_IMPLS: dict[str, Callable[[AgentContext, dict], dict]] = {
    "search_tax_law": _tool_search,
    "calculate_tax": _tool_calculate,
    "what_if": _tool_what_if,
    "get_my_profile": _tool_profile,
}


def run_tool(ctx: AgentContext, name: str, raw_args: Any) -> str:
    try:
        args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
    except json.JSONDecodeError:
        args = {}
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        result: dict = {"error": f"Unknown tool {name}"}
    else:
        try:
            result = impl(ctx, args)
        except Exception as exc:  # validation errors etc. go back to the model
            result = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}
    ctx.steps.append({"tool": name, "args": {k: v for k, v in args.items() if k != "base_profile"}, "ok": "error" not in result})
    text = json.dumps(result, ensure_ascii=False)[:TOOL_RESULT_CHAR_LIMIT]
    ctx.tool_texts.append(text)
    return text


# ── grounding check ───────────────────────────────────────────────────────────
def _numbers_in(text: str) -> set[int]:
    out = set()
    for m in _NUM_RE.findall(text):
        try:
            out.add(int(round(float(m.replace(",", "")))))
        except ValueError:
            pass
    return out


def ungrounded_amounts(answer: str, ctx: AgentContext) -> list[int]:
    """₹ amounts in the answer that appear in no tool result or retrieved law text."""
    known = set()
    for t in ctx.tool_texts:
        known |= _numbers_in(t)
    for c in ctx.chunks_seen:
        known |= _numbers_in(c.get("text", ""))
    bad = []
    for groups in _RUPEE_RE.findall(answer):
        m = groups[0] or groups[1]
        v = int(round(float(m.replace(",", ""))))
        if v == 0 or v in known or any(abs(v - k) <= 1 for k in known):
            continue
        bad.append(v)
    return bad


# ── the loop ──────────────────────────────────────────────────────────────────
ChatFn = Callable[..., Awaitable[Any]]


def _msg_to_dict(msg: Any) -> dict:
    tool_calls = []
    for tc in getattr(msg, "tool_calls", None) or []:
        # Start from the provider's own serialisation so extra fields survive the
        # round trip — Gemini 3 rejects tool calls sent back without their
        # `extra_content.google.thought_signature`.
        base = tc.model_dump(exclude_none=True) if hasattr(tc, "model_dump") else {}
        base.update({
            "id": tc.id, "type": "function",
            "function": {"name": tc.function.name, "arguments": tc.function.arguments
                         if isinstance(tc.function.arguments, str) else json.dumps(tc.function.arguments)},
        })
        tool_calls.append(base)
    d = {"role": "assistant", "content": getattr(msg, "content", "") or ""}
    if tool_calls:
        d["tool_calls"] = tool_calls
    return d


async def run_agent(
    chat: ChatFn,
    model: str,
    question: str,
    retriever: Any,
    profile: Optional[UserFinancialProfile] = None,
    history: Optional[list[dict]] = None,
    on_step: Optional[Callable[[dict], Awaitable[None]]] = None,
) -> dict:
    """
    chat: an async callable with the signature of `LLMClient.chat.complete_async` (backend/llm.py).
    Returns {answer, citations, steps, grounded, confidence, tool_calls}.
    """
    ctx = AgentContext(retriever=retriever, profile=profile)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if profile is not None:
        messages.append({"role": "system", "content": "A saved profile is available via get_my_profile / what_if."})
    for h in (history or [])[-6:]:
        messages.append({"role": h["role"], "content": h["content"][:1500]})
    messages.append({"role": "user", "content": question})

    tool_calls_used = 0
    answer = ""
    while True:
        force_answer = tool_calls_used >= MAX_TOOL_CALLS
        resp = await chat(
            model=model, messages=messages, tools=TOOLS,
            tool_choice="none" if force_answer else "auto",
            temperature=0.1, max_tokens=450,
        )
        msg = resp.choices[0].message
        calls = getattr(msg, "tool_calls", None) or []
        if not calls or force_answer:
            answer = (getattr(msg, "content", "") or "").strip()
            break
        messages.append(_msg_to_dict(msg))
        for tc in calls:
            if tool_calls_used >= MAX_TOOL_CALLS:
                content = json.dumps({"error": "Tool budget exhausted — answer now with what you have."})
            else:
                tool_calls_used += 1
                content = await asyncio.to_thread(run_tool, ctx, tc.function.name, tc.function.arguments)
                if on_step:
                    await on_step(ctx.steps[-1])
            messages.append({"role": "tool", "name": tc.function.name, "content": content, "tool_call_id": tc.id})

    if _too_long_or_formatted(answer):
        messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "user", "content": (
            f"Rewrite that answer in at most {TARGET_WORDS} words as plain sentences: no headings, lists, "
            "tables or bold. Keep the direct answer, the before and after figures of any comparison, and the "
            "citations. Write amounts with the ₹ symbol and Indian digit grouping, e.g. ₹1,56,000.")})
        resp = await chat(model=model, messages=messages, tools=TOOLS, tool_choice="none", temperature=0.0, max_tokens=450)
        answer = (getattr(resp.choices[0].message, "content", "") or "").strip() or answer

    bad = ungrounded_amounts(answer, ctx)
    if bad:
        messages.append({"role": "assistant", "content": answer})
        messages.append({"role": "user", "content": (
            f"These amounts do not appear in any tool result: {', '.join(f'₹{b:,}' for b in bad)}. "
            "Rewrite the answer using only amounts from tool results; drop any figure you cannot support.")})
        resp = await chat(model=model, messages=messages, tools=TOOLS, tool_choice="none", temperature=0.0, max_tokens=450)
        answer = (getattr(resp.choices[0].message, "content", "") or "").strip()
        bad = ungrounded_amounts(answer, ctx)

    seen, citations = set(), []
    for c in ctx.chunks_seen:
        if c["section_ref"] not in seen:
            seen.add(c["section_ref"])
            citations.append({"section": c["section_ref"], "excerpt": c["text"][:200], "source": c["source_file"]})

    used_engine = any(s["tool"] in ("calculate_tax", "what_if") and s["ok"] for s in ctx.steps)
    return {
        "answer": answer,
        "citations": citations[:6],
        "steps": ctx.steps,
        "tool_calls": tool_calls_used,
        "grounded": not bad,
        "confidence": "high" if not bad and (citations or used_engine) else "low",
    }
