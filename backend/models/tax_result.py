"""ORM model for tax_results, one row per profile."""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class TaxResultORM(Base):
    """
    A regime comparison result. result_data holds the full TaxResult;
    recommended_regime is copied out so it can be queried without parsing JSONB.
    """
    __tablename__ = "tax_results"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    profile_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        nullable=False,
        index=True,
        unique=True,     # One result per profile
        comment="References profiles.id — one-to-one relationship",
    )
    result_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Full TaxResult serialized as JSONB",
    )
    recommended_regime: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        comment="'old' or 'new' — denormalized for analytics queries",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
