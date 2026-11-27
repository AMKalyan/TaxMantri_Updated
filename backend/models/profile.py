"""
ORM model for profiles.

Financial data lives in a single JSONB column so salary figures never show
up in WHERE clauses in SQL logs.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ProfileORM(Base):
    """A user's financial profile, stored as a JSONB blob in profile_data."""
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="UUID primary key — matches UserFinancialProfile.profile_id",
    )
    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
        comment="Session that created this profile — used for wizard flow lookup",
    )
    profile_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Full UserFinancialProfile serialized as JSONB. All financial data in blob.",
    )
    input_method: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="'ocr' or 'manual' — mirrors InputMethod enum",
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
