"""
POST /api/assistant — tool-using tax assistant (see agent.py).

Returns JSON by default. With `?stream=true` it returns Server-Sent Events:
  event: step   data: {"tool": "...", "args": {...}, "ok": true}   (one per tool call)
  event: done   data: {answer, citations, steps, grounded, confidence}
  event: error  data: {"message": "..."}
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.assistant.agent import run_agent
from backend.agents.matcher_agent.schemas import QueryRequest
from backend.config import settings
from backend.database import AsyncSessionLocal, get_db
from backend.ratelimit import rate_limit
from backend.store import get_chat_history, get_profile, save_chat_message

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Assistant"])


async def _history(db: AsyncSession, session_id: str) -> list[dict]:
    rows = await get_chat_history(db, session_id)
    out: list[dict] = []
    for r in rows[-3:]:
        out += [{"role": "user", "content": r["question"]}, {"role": "assistant", "content": r["answer"]}]
    return out


@router.post(
    "/assistant",
    dependencies=[Depends(rate_limit("assistant", per_minute=6, per_day=60, global_bucket="llm"))],
)
async def assistant(
    body: QueryRequest,
    request: Request,
    stream: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    state = request.app.state
    if getattr(state, "llm", None) is None:
        raise HTTPException(status_code=503, detail="The AI assistant is not configured on this server.")

    profile = await get_profile(db, body.profile_id) if body.profile_id else None
    history = await _history(db, body.session_id)
    chat = state.llm.chat.complete_async
    semaphore: Optional[asyncio.Semaphore] = getattr(state, "rag_semaphore", None)

    async def _run(on_step=None) -> dict:
        async def guarded_chat(**kw):
            if semaphore is None:
                return await chat(**kw)
            async with semaphore:
                return await chat(**kw)
        return await asyncio.wait_for(
            run_agent(guarded_chat, settings.chat_model, body.question,
                      getattr(state, "retriever", None), profile, history, on_step),
            timeout=60,
        )

    async def _persist(result: dict) -> None:
        async with AsyncSessionLocal() as s:
            await save_chat_message(s, body.session_id, body.question, result["answer"], result["confidence"])
            await s.commit()

    if not stream:
        try:
            result = await _run()
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="The assistant took too long. Please try again.")
        await _persist(result)
        return JSONResponse(result)

    queue: asyncio.Queue = asyncio.Queue()

    async def producer():
        try:
            result = await _run(on_step=lambda s: queue.put(("step", s)))
            await _persist(result)
            await queue.put(("done", result))
        except asyncio.TimeoutError:
            await queue.put(("error", {"message": "The assistant took too long. Please try again."}))
        except Exception:
            logger.exception("assistant stream failed")
            await queue.put(("error", {"message": "Something went wrong. Please try again."}))

    async def events():
        task = asyncio.create_task(producer())
        try:
            while True:
                kind, data = await queue.get()
                yield f"event: {kind}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                if kind in ("done", "error"):
                    break
        finally:
            task.cancel()

    return StreamingResponse(
        events(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
