"""
ORM model for session_events: one row per frontend UI event. Used for the
session context in the chat prompt and for GET /api/session/summary.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class SessionEventORM(Base):
    """
    A single UI event. payload is small structured context such as
    {"tab": "deductions"}, never PAN, names or other PII.
    """
    __tablename__ = "session_events"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID row identifier",
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="Session identifier — groups events by user session",
    )
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Category of UI action: tab_click, page_view, pdf_download, regime_compare",
    )
    payload: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Structured event context. Must not contain PAN or taxpayer name.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
