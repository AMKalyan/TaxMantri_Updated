"""
Privacy endpoints and retention.

DELETE /api/my-data   {profile_id?, session_id?}  → removes all stored data for them.
IDs are random UUIDs held only by the user's browser, so knowing them is the
capability to delete. A background task also purges everything older than
DATA_RETENTION_HOURS (default 24) at startup and hourly while the server is awake.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import AsyncSessionLocal, get_db
from backend.ratelimit import rate_limit
from backend.store import delete_user_data, purge_expired

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Privacy"])


class DeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    profile_id: Optional[str] = Field(default=None, max_length=64)
    session_id: Optional[str] = Field(default=None, max_length=64)


@router.delete("/my-data", dependencies=[Depends(rate_limit("delete", per_minute=10))])
async def delete_my_data(body: DeleteRequest, db: AsyncSession = Depends(get_db)) -> dict:
    if not body.profile_id and not body.session_id:
        raise HTTPException(status_code=400, detail="Provide profile_id and/or session_id.")
    counts = await delete_user_data(db, body.profile_id, body.session_id)
    return {"deleted": counts, "retention_hours": settings.data_retention_hours}


async def retention_loop() -> None:
    while True:
        try:
            async with AsyncSessionLocal() as s:
                await purge_expired(s, settings.data_retention_hours)
                await s.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Retention purge failed: %s", exc)
        await asyncio.sleep(3600)
