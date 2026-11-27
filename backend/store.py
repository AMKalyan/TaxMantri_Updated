"""
Data access functions used by the routes, so they don't deal with
SQLAlchemy directly. Functions take an AsyncSession and return Pydantic
objects or plain dicts, not ORM instances.

Log only IDs — never salary values, PAN or names.
"""

# Writes commit before returning: the get_db() commit runs after the response is
# sent, so a client calling straight back (confirm -> calculate) could miss the row.

import logging
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.evaluator_agent.schemas import TaxResult
from backend.agents.input_agent.schemas import UserFinancialProfile
from backend.models.chat_history import ChatHistoryORM
from backend.models.profile import ProfileORM
from backend.models.session import SessionORM
from backend.models.session_event import SessionEventORM
from backend.models.tax_result import TaxResultORM

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Profile operations
# ---------------------------------------------------------------------------

async def save_profile(
    db: AsyncSession,
    profile: UserFinancialProfile,
    session_id: str = "",
) -> str:
    """
    Save a profile and return its profile_id.
    """
    orm = ProfileORM(
        id=profile.profile_id,
        session_id=session_id,
        profile_data=profile.model_dump(),
        input_method=profile.input_method.value,
    )
    db.add(orm)
    await db.commit()
    logger.info("Saved profile profile_id=%s input_method=%s", profile.profile_id, profile.input_method.value)
    return profile.profile_id


async def get_profile(
    db: AsyncSession,
    profile_id: str,
) -> Optional[UserFinancialProfile]:
    """Return the profile with this id, or None."""
    result = await db.execute(
        select(ProfileORM).where(ProfileORM.id == profile_id)
    )
    orm = result.scalar_one_or_none()
    if orm is None:
        return None
    return UserFinancialProfile.model_validate(orm.profile_data)


# ---------------------------------------------------------------------------
# Tax result operations
# ---------------------------------------------------------------------------

async def save_result(db: AsyncSession, result: TaxResult) -> None:
    """
    Save the TaxResult for a profile, replacing any existing one (there is one
    result per profile).
    """
    existing = await db.execute(
        select(TaxResultORM).where(TaxResultORM.profile_id == result.profile_id)
    )
    orm = existing.scalar_one_or_none()

    if orm is None:
        orm = TaxResultORM(
            profile_id=result.profile_id,
            result_data=result.model_dump(),
            recommended_regime=result.recommended_regime,
        )
        db.add(orm)
    else:
        orm.result_data = result.model_dump()
        orm.recommended_regime = result.recommended_regime

    await db.commit()
    logger.info(
        "Saved tax result profile_id=%s recommended_regime=%s",
        result.profile_id,
        result.recommended_regime,
    )


async def get_result(
    db: AsyncSession,
    profile_id: str,
) -> Optional[TaxResult]:
    """Return the stored TaxResult for a profile, or None if not calculated yet."""
    result = await db.execute(
        select(TaxResultORM).where(TaxResultORM.profile_id == profile_id)
    )
    orm = result.scalar_one_or_none()
    if orm is None:
        return None
    return TaxResult.model_validate(orm.result_data)


# ---------------------------------------------------------------------------
# Session state operations
# ---------------------------------------------------------------------------

async def get_session(
    db: AsyncSession,
    session_id: str,
) -> Optional[dict]:
    """
    Return wizard progress from Postgres, or None. Redis (cache.py) is the
    primary store; this is the durable copy.
    """
    result = await db.execute(
        select(SessionORM).where(SessionORM.id == session_id)
    )
    orm = result.scalar_one_or_none()
    if orm is None:
        return None
    return orm.data


async def set_session(
    db: AsyncSession,
    session_id: str,
    data: dict,
) -> None:
    """
    Upsert wizard progress in Postgres. The caller writes the Redis copy separately.
    """
    result = await db.execute(
        select(SessionORM).where(SessionORM.id == session_id)
    )
    orm = result.scalar_one_or_none()

    if orm is None:
        orm = SessionORM(id=session_id, data=data)
        db.add(orm)
    else:
        orm.data = data  # SQLAlchemy detects mutation and marks dirty

    await db.commit()
    logger.info("Updated session session_id=%s", session_id)


# ---------------------------------------------------------------------------
# Chat history operations
# ---------------------------------------------------------------------------

async def save_chat_message(
    db: AsyncSession,
    session_id: str,
    question: str,
    answer: str,
    confidence: str,
) -> None:
    """
    Save one Q&A exchange. Called for every answer, including cache hits and
    low-confidence ones. The question text isn't logged since it may contain PII.
    """
    orm = ChatHistoryORM(
        id=str(uuid.uuid4()),
        session_id=session_id,
        question=question,
        answer=answer,
        confidence=confidence,
    )
    db.add(orm)
    await db.commit()
    logger.info("Saved chat message session_id=%s confidence=%s", session_id, confidence)


async def get_chat_history(
    db: AsyncSession,
    session_id: str,
) -> list[dict]:
    """Return a session's Q&A exchanges, oldest first."""
    result = await db.execute(
        select(ChatHistoryORM)
        .where(ChatHistoryORM.session_id == session_id)
        .order_by(ChatHistoryORM.created_at.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "question": row.question,
            "answer": row.answer,
            "confidence": row.confidence,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Session event operations
# ---------------------------------------------------------------------------

async def save_session_event(
    db: AsyncSession,
    session_id: str,
    event_type: str,
    payload: dict,
) -> None:
    """
    Save one UI event. The payload should hold only things like tab or regime
    names, and is not logged.
    """
    orm = SessionEventORM(
        id=str(uuid.uuid4()),
        session_id=session_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(orm)
    await db.commit()
    logger.info("Saved session event session_id=%s event_type=%s", session_id, event_type)


async def get_session_events(
    db: AsyncSession,
    session_id: str,
) -> list[dict]:
    """Return a session's UI events, oldest first."""
    result = await db.execute(
        select(SessionEventORM)
        .where(SessionEventORM.session_id == session_id)
        .order_by(SessionEventORM.created_at.asc())
    )
    rows = result.scalars().all()
    return [
        {
            "event_type": row.event_type,
            "payload": row.payload,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


# Topic keyword mapping — used by get_session_summary to tag questions by subject
_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "HRA": ["hra", "house rent", "rent allowance"],
    "80C": ["80c", "ppf", "elss", "nsc", "life insurance"],
    "NPS": ["nps", "national pension", "80ccd"],
    "80D": ["80d", "health insurance", "medical insurance"],
    "Home Loan": ["home loan", "housing loan", "section 24", "interest on loan"],
    "Standard Deduction": ["standard deduction"],
    "Regime": ["regime", "old regime", "new regime"],
    "Tax Slabs": ["slab", "tax rate", "income tax rate"],
    "ITR-1": ["itr", "itr-1", "income tax return", "filing"],
    "Capital Gains": ["capital gain", "ltcg", "stcg"],
}


def _extract_topics(questions: list[str]) -> list[str]:
    """Return topic labels that appear in any of the questions (case-insensitive)."""
    combined = " ".join(questions).lower()
    return [
        topic
        for topic, keywords in _TOPIC_KEYWORDS.items()
        if any(kw in combined for kw in keywords)
    ]


async def get_session_summary(
    db: AsyncSession,
    session_id: str,
) -> dict:
    """
    Summarise a session from its chat history and UI events: question count,
    share of high-confidence answers, topics, tabs and pages visited, whether
    a PDF was downloaded, and duration from first to last activity.
    """
    chat_rows = await get_chat_history(db, session_id)
    event_rows = await get_session_events(db, session_id)

    # ── Chat metrics ────────────────────────────────────────────────────────
    question_count = len(chat_rows)
    high_count = sum(1 for r in chat_rows if r["confidence"] == "high")
    high_confidence_pct = round(high_count / question_count * 100, 1) if question_count else 0.0
    topics_asked = _extract_topics([r["question"] for r in chat_rows])

    # ── UI event metrics ─────────────────────────────────────────────────────
    tabs_visited = list({
        e["payload"].get("tab")
        for e in event_rows
        if e["event_type"] == "tab_click" and e["payload"].get("tab")
    })
    pdf_downloaded = any(e["event_type"] == "pdf_download" for e in event_rows)
    regime_compared = any(e["event_type"] == "regime_compare" for e in event_rows)
    pages_visited = list({
        e["payload"].get("page")
        for e in event_rows
        if e["event_type"] == "page_view" and e["payload"].get("page")
    })

    # ── Session duration ─────────────────────────────────────────────────────
    all_timestamps = [r["created_at"] for r in chat_rows] + [e["created_at"] for e in event_rows]
    started_at = min(all_timestamps) if all_timestamps else None
    last_active_at = max(all_timestamps) if all_timestamps else None
    if started_at and last_active_at:
        from datetime import datetime as _dt
        fmt = "%Y-%m-%dT%H:%M:%S.%f%z" if "." in started_at else "%Y-%m-%dT%H:%M:%S%z"
        try:
            t0 = _dt.fromisoformat(started_at)
            t1 = _dt.fromisoformat(last_active_at)
            duration_s = int((t1 - t0).total_seconds())
        except ValueError:
            duration_s = 0
    else:
        duration_s = 0

    return {
        "session_id": session_id,
        "started_at": started_at,
        "last_active_at": last_active_at,
        "duration_seconds": duration_s,
        "question_count": question_count,
        "high_confidence_pct": high_confidence_pct,
        "topics_asked": topics_asked,
        "tabs_visited": tabs_visited,
        "pdf_downloaded": pdf_downloaded,
        "regime_compared": regime_compared,
        "pages_visited": pages_visited,
        "chat_history": chat_rows,
    }


# ---------------------------------------------------------------------------
# Privacy: user-initiated deletion and time-based retention
# ---------------------------------------------------------------------------

async def delete_user_data(
    db: AsyncSession,
    profile_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """
    Delete everything tied to a profile and/or session: tax results, profiles,
    chat history and UI events. Returns row counts per table.
    """
    from sqlalchemy import delete, or_

    counts: dict[str, int] = {}
    profile_ids: list[str] = []
    if profile_id:
        profile_ids.append(profile_id)
    if session_id:
        rows = await db.execute(select(ProfileORM.id).where(ProfileORM.session_id == session_id))
        profile_ids += [r[0] for r in rows]
    if profile_ids:
        counts["tax_results"] = (await db.execute(
            delete(TaxResultORM).where(TaxResultORM.profile_id.in_(profile_ids)))).rowcount or 0
        counts["profiles"] = (await db.execute(
            delete(ProfileORM).where(ProfileORM.id.in_(profile_ids)))).rowcount or 0
    if session_id:
        counts["chat_history"] = (await db.execute(
            delete(ChatHistoryORM).where(ChatHistoryORM.session_id == session_id))).rowcount or 0
        counts["session_events"] = (await db.execute(
            delete(SessionEventORM).where(SessionEventORM.session_id == session_id))).rowcount or 0
    await db.commit()
    logger.info("User data deleted counts=%s", counts)
    return counts


async def purge_expired(db: AsyncSession, hours: int) -> dict:
    """Delete rows older than `hours` from every table holding user data."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import delete

    if hours <= 0:
        return {}
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    counts = {}
    for name, orm in (
        ("tax_results", TaxResultORM),
        ("chat_history", ChatHistoryORM),
        ("session_events", SessionEventORM),
        ("profiles", ProfileORM),
        ("sessions", SessionORM),
    ):
        counts[name] = (await db.execute(delete(orm).where(orm.created_at < cutoff))).rowcount or 0
    await db.commit()
    if any(counts.values()):
        logger.info("Retention purge (>%sh) deleted %s", hours, counts)
    return counts
