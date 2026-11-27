"""
Redis helpers.

Keys:
  session:{session_id}     wizard progress, 24h TTL
  faq:{sha256(question)}   cached answer, 1h TTL

The client comes from redis.asyncio (part of redis-py), is created once in the
lifespan hook and passed into each helper. Only keys and IDs are logged.
"""
import hashlib
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TTL constants (seconds)
# ---------------------------------------------------------------------------
SESSION_TTL: int = 86400   # 24 hours
FAQ_TTL: int = 3600        # 1 hour

# ---------------------------------------------------------------------------
# Key prefix constants
# ---------------------------------------------------------------------------
SESSION_PREFIX = "session"
FAQ_PREFIX = "faq"


# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------

def make_session_key(session_id: str) -> str:
    """Build Redis key for session wizard progress: session:{session_id}"""
    return f"{SESSION_PREFIX}:{session_id}"


def make_faq_key(question: str) -> str:
    """FAQ cache key: faq:{sha256 of the stripped, lowercased question}."""
    normalized = question.strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{FAQ_PREFIX}:{digest}"


# ---------------------------------------------------------------------------
# Pool factory — called once in lifespan
# ---------------------------------------------------------------------------

async def create_redis_pool() -> aioredis.Redis:
    """Create the async Redis client and check it with PING."""
    from urllib.parse import urlsplit

    url = settings.redis_connection_url
    client = aioredis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
        health_check_interval=30,   # hosted Redis (Upstash) drops idle connections
        socket_keepalive=True,
    )
    parts = urlsplit(url)
    try:
        await client.ping()
    except Exception as exc:
        # Say what went wrong without printing the password in the URL.
        raise RuntimeError(
            f"Could not connect to Redis at {parts.scheme}://{parts.hostname}:{parts.port} ({exc}). "
            "Check REDIS_URL; hosted Redis such as Upstash needs a rediss:// (TLS) URL."
        ) from exc
    logger.info("Redis connection pool established at %s (tls=%s)", parts.hostname, parts.scheme == "rediss")
    return client


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

async def get_session_data(
    client: aioredis.Redis, session_id: str
) -> Optional[dict]:
    """
    Retrieve wizard progress dict from Redis.
    Returns None if session expired or never existed.
    """
    key = make_session_key(session_id)
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_session_data(
    client: aioredis.Redis, session_id: str, data: dict
) -> None:
    """
    Store wizard progress with a fresh 24h TTL. The caller also saves it to
    Postgres via store.set_session().
    """
    key = make_session_key(session_id)
    await client.setex(key, SESSION_TTL, json.dumps(data))
    logger.info("Session data updated session_id=%s ttl=%ds", session_id, SESSION_TTL)


# ---------------------------------------------------------------------------
# FAQ cache helpers
# ---------------------------------------------------------------------------

async def get_faq_cache(
    client: aioredis.Redis, question: str
) -> Optional[dict]:
    """Return the cached answer dict for this question, or None."""
    key = make_faq_key(question)
    raw = await client.get(key)
    if raw is None:
        return None
    logger.info("FAQ cache hit key=%s", key)
    return json.loads(raw)


async def set_faq_cache(
    client: aioredis.Redis, question: str, response: dict
) -> None:
    """Cache an answer dict for an hour."""
    key = make_faq_key(question)
    await client.setex(key, FAQ_TTL, json.dumps(response))
    logger.info("FAQ response cached key=%s ttl=%ds", key, FAQ_TTL)
