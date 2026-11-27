"""
ORM model for chat_history: one row per Q&A exchange, including
low-confidence and out-of-KB answers.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ChatHistoryORM(Base):
    """A single Q&A exchange within a session."""
    __tablename__ = "chat_history"

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
        comment="Session identifier — groups messages by user session",
    )
    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="User's question text",
    )
    answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Generated answer text (may be low-confidence or out-of-KB)",
    )
    confidence: Mapped[str] = mapped_column(
        String(4),
        nullable=False,
        comment="'high' or 'low' — from ConfidenceLevel enum",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
