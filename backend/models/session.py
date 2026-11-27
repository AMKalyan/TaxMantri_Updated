"""
ORM model for sessions (wizard progress).

Redis holds the live copy with a 24h TTL; this table is the durable copy
that survives Redis restarts.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class SessionORM(Base):
    """
    Wizard progress for a session. data holds things like the current step and
    partial profile fields, never PAN, names or other identifying data.
    """
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        comment="Session UUID — matches the Redis key 'session:{id}'",
    )
    data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        comment="Wizard progress state. Must not contain PAN or taxpayer name.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
