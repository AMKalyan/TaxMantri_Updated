"""Agent-loop tests against a scripted fake LLM client (no network)."""
import asyncio
import json
from types import SimpleNamespace as NS

from backend.agents.assistant.agent import MAX_TOOL_CALLS, run_agent
from backend.agents.input_agent.schemas import UserFinancialProfile


def _call(name, args, i=0):
    return NS(id=f"call_{name}_{i}", function=NS(name=name, arguments=json.dumps(args)))


def _resp(content="", calls=None):
    return NS(choices=[NS(message=NS(content=content, tool_calls=calls))])


class FakeChat:
    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    async def __call__(self, **kw):
        self.requests.append(kw)
        step = self.script.pop(0)
        return step(kw) if callable(step) else step


class FakeRetriever:
    def hybrid_search(self, q, top_k=4):
        return [{"chunk_id": "c1", "section_ref": "IT Act S.80CCD", "source_file": "section_80ccd.txt",
                 "text": "80CCD(1B): additional deduction up to ₹50,000 for NPS contributions."}]


PROFILE = UserFinancialProfile(basic_salary=1_800_000, input_method="manual", city_type="metro", age_bracket="under60")


def run(chat, **kw):
    return asyncio.run(run_agent(chat, "test-model", kw.pop("q", "question"), FakeRetriever(), **kw))


def test_what_if_numbers_come_from_engine():
    def answer_from_tool(kw):
        tool_msg = json.loads(kw["messages"][-1]["content"])
        old_before = tool_msg["before"]["old_regime"]["total_tax"]
        old_after = tool_msg["after"]["old_regime"]["total_tax"]
        return _resp(f"Old regime tax drops from ₹{old_before:,} to ₹{old_after:,} [Section 80CCD, IT Act 1961].")

    chat = FakeChat([
        _resp(calls=[_call("what_if", {"changes": {"employee_nps_80ccd1b": 50_000}})]),
        answer_from_tool,
    ])
    out = run(chat, profile=PROFILE, q="What if I put 50k in NPS?")
    assert out["grounded"] is True
    assert out["steps"][0]["tool"] == "what_if" and out["steps"][0]["ok"]
    assert out["tool_calls"] == 1


def test_tool_budget_is_enforced():
    looping = [_resp(calls=[_call("search_tax_law", {"query": "x"}, i)]) for i in range(MAX_TOOL_CALLS)]
    final = lambda kw: _resp("Here is the answer.") if kw["tool_choice"] == "none" else _resp(calls=[_call("search_tax_law", {"query": "y"}, 99)])
    chat = FakeChat(looping + [final])
    out = run(chat)
    assert out["tool_calls"] == MAX_TOOL_CALLS
    assert chat.requests[-1]["tool_choice"] == "none"
    assert out["answer"] == "Here is the answer."


def test_invented_amount_triggers_retry_and_flag():
    chat = FakeChat([
        _resp("You will save exactly ₹73,219 by switching."),          # invented
        _resp("You would save ₹73,219."),                              # still invented after retry
    ])
    out = run(chat)
    assert out["grounded"] is False
    assert out["confidence"] == "low"
    assert "do not appear in any tool result" in chat.requests[-1]["messages"][-1]["content"]


def test_law_amounts_are_allowed():
    chat = FakeChat([
        _resp(calls=[_call("search_tax_law", {"query": "nps extra deduction"})]),
        _resp("Section 80CCD(1B) allows up to ₹50,000 extra [Section 80CCD, IT Act 1961]."),
    ])
    out = run(chat)
    assert out["grounded"] is True
    assert out["citations"][0]["section"] == "IT Act S.80CCD"


def test_bad_tool_args_are_reported_to_model_not_raised():
    chat = FakeChat([
        _resp(calls=[_call("calculate_tax", {"basic_salary": -5})]),
        _resp("I need a valid salary to calculate."),
    ])
    out = run(chat)
    assert out["steps"][0]["ok"] is False
    assert "error" in chat.requests[-1]["messages"][-1]["content"]


def test_what_if_without_profile_asks_for_data():
    chat = FakeChat([
        _resp(calls=[_call("what_if", {"changes": {"investments_80c": 150_000}})]),
        _resp("Please share your salary first."),
    ])
    out = run(chat)
    assert out["steps"][0]["ok"] is False


def test_long_markdown_answer_is_rewritten():
    long_md = "### Breakdown\n" + " ".join(["word"] * 150)
    chat = FakeChat([_resp(long_md), _resp("Short plain answer.")])
    out = run(chat)
    assert out["answer"] == "Short plain answer."
    assert "at most 90 words" in chat.requests[-1]["messages"][-1]["content"]


def test_amounts_written_as_rupees_are_still_checked():
    chat = FakeChat([_resp("You save 73,219 rupees."), _resp("You save 73,219 rupees.")])
    out = run(chat)
    assert out["grounded"] is False
