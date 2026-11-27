"""
llm.py — the Gemini chat client used across the app.

Gemini is called through Google's OpenAI-compatible endpoint. Callers use one
small interface:

    client = make_llm_client()
    resp = await client.chat.complete_async(model=..., messages=[...], tools=[...],
                                            tool_choice="auto", temperature=0.1, max_tokens=300)
    resp.choices[0].message.content / .tool_calls[i].id / .function.name / .function.arguments
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from backend.config import settings

logger = logging.getLogger(__name__)

GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


class _GeminiChat:
    def __init__(self, client: Any, reasoning_effort: Optional[str]) -> None:
        self._client = client
        self._reasoning_effort = reasoning_effort

    async def complete_async(self, *, model: str, messages: list[dict], tools: Optional[list] = None,
                             tool_choice: Optional[str] = None, temperature: float = 0.2,
                             max_tokens: int = 300) -> Any:
        # Tool-result messages are matched by tool_call_id; the endpoint rejects a "name" field.
        clean = [
            {k: v for k, v in m.items() if not (m.get("role") == "tool" and k == "name")}
            for m in messages
        ]
        kwargs: dict[str, Any] = dict(model=model, messages=clean, temperature=temperature, max_tokens=max_tokens)
        if tools:
            kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
        if self._reasoning_effort:
            kwargs["reasoning_effort"] = self._reasoning_effort
        return await self._client.chat.completions.create(**kwargs)


class LLMClient:
    def __init__(self, chat: Any) -> None:
        self.chat = chat


def make_llm_client() -> Optional[LLMClient]:
    """Return a Gemini client, or None if GEMINI_API_KEY is not set (AI features are then disabled)."""
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set — AI features disabled")
        return None
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.gemini_api_key, base_url=GEMINI_OPENAI_BASE_URL, timeout=45, max_retries=2)
    return LLMClient(_GeminiChat(client, settings.gemini_reasoning_effort or None))
