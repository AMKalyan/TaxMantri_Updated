"""Import every ORM model so Alembic sees them on Base.metadata."""
from backend.models.profile import ProfileORM
from backend.models.session import SessionORM
from backend.models.tax_result import TaxResultORM
from backend.models.chat_history import ChatHistoryORM
from backend.models.session_event import SessionEventORM

__all__ = ["ProfileORM", "TaxResultORM", "SessionORM", "ChatHistoryORM", "SessionEventORM"]
