"""
Tax Q&A routes:

POST /api/query           cached or retrieved-and-generated answer
GET  /api/chat/history    a session's Q&A history
POST /api/session/event   record a UI event (tab_click, pdf_download, ...)
GET  /api/session/summary derived session metrics

There is no user authentication. The retriever, LLM client and semaphore on
app.state are set up in the lifespan hook in main.py.
"""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.matcher_agent.llm_service import build_profile_summary, generate_answer
from backend.agents.matcher_agent.retriever import TaxRetriever
from backend.agents.matcher_agent.schemas import QueryRequest, RAGResponse, SessionEventRequest
from backend.cache import get_faq_cache, set_faq_cache
from backend.database import get_db
from backend.ratelimit import rate_limit
from backend.store import (
    get_chat_history,
    get_profile,
    get_session_events,
    get_session_summary,
    save_chat_message,
    save_session_event,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Matcher Agent"])


@router.post("/query", dependencies=[Depends(rate_limit("query", per_minute=10, per_day=100, global_bucket="llm"))])
async def query_endpoint(
    body: QueryRequest,
    request: Request,
    debug: bool = Query(default=False, description="Include top-3 retrieved chunks in response"),
    db: AsyncSession = Depends(get_db),
):
    """
    Answer a tax question from the knowledge base, with [Section X, IT Act 1961]
    citations. Answers are cached in Redis for an hour and every answer,
    cached or not, is saved to chat history.

    Returns 503 if the retrieval index isn't loaded. There's no response_model
    because the debug path returns a JSONResponse with retrieved_chunks added.
    """
    redis = request.app.state.redis

    # ── 1. FAQ cache check ──────────────────────────────────────────────────
    cached_data = await get_faq_cache(redis, body.question)
    if cached_data is not None:
        logger.info("FAQ cache hit for session_id=%s", body.session_id)
        cached_data["cached"] = True
        # Cache hits are recorded too, so the history is complete.
        await save_chat_message(
            db,
            body.session_id,
            body.question,
            cached_data.get("answer", ""),
            cached_data.get("confidence", "low"),
        )
        return RAGResponse(**cached_data)

    # ── 2. Retrieval ────────────────────────────────────────────────────────
    retriever: Optional[TaxRetriever] = request.app.state.retriever
    if retriever is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "RAG knowledge base is not available. "
                "Run: python backend/agents/matcher_agent/build_index.py to build indexes."
            ),
        )
    from fastapi.concurrency import run_in_threadpool
    chunks = await run_in_threadpool(retriever.hybrid_search, body.question, 10)
    logger.info("Retrieval complete session_id=%s chunks=%d", body.session_id, len(chunks))

    # ── 3. Profile summary (numbers only, no PII) ─────────────────────────
    profile_summary: Optional[str] = None
    if body.profile_id:
        profile = await get_profile(db, body.profile_id)
        if profile is not None:
            profile_summary = build_profile_summary(profile)

    # ── 3b. Session context from events and prior chat (no PII) ───────────
    session_context: Optional[str] = None
    try:
        events = await get_session_events(db, body.session_id)
        prior_chat = await get_chat_history(db, body.session_id)
        prior_count = len(prior_chat)
        if prior_count > 0 or events:
            tabs = list({
                e["payload"].get("tab")
                for e in events
                if e["event_type"] == "tab_click" and e["payload"].get("tab")
            })
            pdf_dl = any(e["event_type"] == "pdf_download" for e in events)
            parts = [f"Prior questions: {prior_count}"]
            if tabs:
                parts.append(f"Tabs viewed: {', '.join(tabs)}")
            if pdf_dl:
                parts.append("PDF downloaded: yes")
            session_context = " | ".join(parts)
    except Exception:
        pass  # session context is optional; don't fail the answer over it

    # ── 4. LLM generation + citation validation ─────────────────────────
    llm = request.app.state.llm
    if llm is None:
        raise HTTPException(status_code=503, detail="The AI assistant is not configured on this server.")
    semaphore: asyncio.Semaphore = request.app.state.rag_semaphore
    result = await generate_answer(
        llm, body.question, chunks, profile_summary, semaphore, session_context
    )
    result["cached"] = False

    # ── 5. Persist to chat_history (cache miss path) ─────────────────────
    await save_chat_message(
        db,
        body.session_id,
        body.question,
        result["answer"],
        result["confidence"],
    )

    # ── 6. Cache the result, without retrieved_chunks ─────────────────────
    cacheable = {k: v for k, v in result.items() if k != "retrieved_chunks"}
    await set_faq_cache(redis, body.question, cacheable)

    # ── 7. Return ─────────────────────────────────────────────────────────
    # RAGResponse has no retrieved_chunks field, so the debug path adds them
    # to a plain JSONResponse instead.
    if debug:
        retrieved_chunks = [
            {
                "section_ref": c.get("section_ref", ""),
                "text_excerpt": c.get("text", "")[:200],
            }
            for c in chunks[:3]
        ]
        rag_fields = {k: v for k, v in result.items() if k != "retrieved_chunks"}
        response_body = RAGResponse(**rag_fields).model_dump()
        response_body["retrieved_chunks"] = retrieved_chunks
        return JSONResponse(content=response_body)

    rag_fields = {k: v for k, v in result.items() if k != "retrieved_chunks"}
    return RAGResponse(**rag_fields)


@router.get("/chat/history")
async def chat_history_endpoint(
    session_id: str = Query(..., description="Session ID to retrieve Q&A history for"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return a session's Q&A exchanges, oldest first (empty if none)."""
    messages = await get_chat_history(db, session_id)
    logger.info("Chat history request session_id=%s messages=%d", session_id, len(messages))
    return {"session_id": session_id, "messages": messages}


@router.post("/session/event", status_code=204)
async def record_session_event(
    body: SessionEventRequest,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Record a UI event (tab_click, page_view, pdf_download, regime_compare,
    chat_open). The payload should hold only tab, page or regime names, no PII.
    """
    await save_session_event(db, body.session_id, body.event_type, body.payload)
    logger.info("Session event recorded session_id=%s event_type=%s", body.session_id, body.event_type)


@router.get("/session/summary")
async def session_summary_endpoint(
    session_id: str = Query(..., description="Session ID to summarise"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Summarise a session from its chat history and events (question count,
    topics, tabs visited, duration, ...). Backs the chat widget's !session command.
    """
    summary = await get_session_summary(db, session_id)
    logger.info(
        "Session summary request session_id=%s questions=%d events=%s",
        session_id,
        summary["question_count"],
        summary["tabs_visited"],
    )
    return summary
