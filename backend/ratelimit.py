"""
ratelimit.py — tiny Redis fixed-window rate limiter used as a FastAPI dependency.

Usage:
    from backend.ratelimit import rate_limit
    @router.post("/query", dependencies=[Depends(rate_limit("query", per_minute=10, per_day=100))])

Keys are per client IP. The leftmost X-Forwarded-For entry is client-controlled
and can be forged, so the IP is read from the right: the entry appended by the
outermost trusted proxy (settings.trusted_proxy_hops). An optional shared
global daily bucket caps total LLM spend regardless of IP.
If Redis is unavailable the limiter fails open (logs a warning).
"""
from __future__ import annotations

import logging
import time

from fastapi import HTTPException, Request

from backend.config import settings

logger = logging.getLogger(__name__)


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    hops = max(0, settings.trusted_proxy_hops)
    if fwd and hops:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if parts:
            return parts[-hops] if len(parts) >= hops else parts[0]
    return request.client.host if request.client else "unknown"


def rate_limit(
    bucket: str,
    per_minute: int,
    per_day: int | None = None,
    global_bucket: str | None = None,
):
    """Return a dependency enforcing per-IP limits for the named bucket."""

    async def _dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        redis = getattr(request.app.state, "redis", None)
        if redis is None:
            return
        ip = client_ip(request)
        now = int(time.time())
        windows = [(f"rl:{bucket}:m:{ip}:{now // 60}", per_minute, 60)]
        if per_day:
            windows.append((f"rl:{bucket}:d:{ip}:{now // 86400}", per_day, 86400))
        if global_bucket:
            windows.append((f"rl:global:{global_bucket}:{now // 86400}", settings.llm_daily_cap, 86400))
        try:
            for key, limit, ttl in windows:
                count = await redis.incr(key)
                if count == 1:
                    await redis.expire(key, ttl)
                if count > limit:
                    if key.startswith("rl:global:"):
                        detail = "TaxMantri's free daily AI quota is used up. Please try again tomorrow."
                    else:
                        span = "minute" if ttl == 60 else "day"
                        detail = f"Too many requests — limit is {limit} per {span}. Please try again later."
                    raise HTTPException(status_code=429, detail=detail)
        except HTTPException:
            raise
        except Exception as exc:  # Redis hiccup → fail open
            logger.warning("Rate limiter unavailable (%s); allowing request", exc)

    return _dependency
