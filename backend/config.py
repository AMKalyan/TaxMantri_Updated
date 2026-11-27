"""
config.py — TaxMantri application settings.

Usage:
    from backend.config import settings
    print(settings.database_url)

All secrets come from environment variables (or a local .env file at the
repository root / backend folder). Never hardcode keys here.
"""
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Later files override earlier ones; real env vars override both.
        env_file=(str(_REPO_ROOT / ".env"), str(_BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Database ---
    # Format: postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME
    database_url: str = "postgresql+asyncpg://taxmantri:taxmantri@localhost:5432/taxmantri"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379"

    # --- Security ---
    secret_key: str = "change-me-in-production-at-least-32-chars"

    # --- Gemini (Google AI Studio key) ---
    gemini_api_key: str = ""
    gemini_chat_model: str = "gemini-3.1-flash-lite"   # fast, reliable tool calls on the free tier
    gemini_embed_model: str = "gemini-embedding-001"
    # "Thinking" budget for chat calls: none | low | medium | high ("" = model default)
    gemini_reasoning_effort: str = "none"

    @property
    def chat_model(self) -> str:
        return self.gemini_chat_model

    # --- CORS ---
    # Comma-separated list of allowed frontend origins
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    # --- OCR binaries (optional; fall back to PATH when unset) ---
    tesseract_cmd: Optional[str] = None
    poppler_path: Optional[str] = None

    # --- Abuse protection ---
    rate_limit_enabled: bool = True
    max_upload_mb: int = 5
    # How many reverse proxies append to X-Forwarded-For in front of the app.
    # The client IP is taken from the right (entries added by trusted proxies),
    # never the leftmost, client-controlled entry.
    trusted_proxy_hops: int = 1
    # Shared ceiling on LLM-backed requests per UTC day across all clients:
    # a backstop that holds even if per-IP detection is wrong.
    # Gemini free tier allows only a few hundred requests/day per project; keep headroom.
    llm_daily_cap: int = 150

    # --- Data retention (hours). 0 disables automatic purge. ---
    data_retention_hours: int = 24

    # --- Application ---
    debug: bool = False
    app_version: str = "0.2.0"

    @property
    def async_database_url(self) -> str:
        """
        Normalise hosted Postgres URLs (Render/Neon give postgres:// or
        postgresql:// with ?sslmode=require) into an asyncpg URL.
        SSL params are stripped here and passed via db_connect_args instead,
        because asyncpg does not understand libpq query params.
        """
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        url = self.database_url
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                url = "postgresql+asyncpg://" + url[len(prefix):]
                break
        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query)
                 if k not in ("sslmode", "channel_binding", "ssl")]
        return urlunsplit(parts._replace(query=urlencode(query)))

    @property
    def db_connect_args(self) -> dict:
        """asyncpg SSL setting derived from the original URL's sslmode/ssl param."""
        lowered = self.database_url.lower()
        if "sslmode=require" in lowered or "sslmode=verify" in lowered or "ssl=true" in lowered or "ssl=require" in lowered:
            return {"ssl": "require"}
        return {}

    @property
    def cors_origins_list(self) -> List[str]:
        """Split comma-separated CORS origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


# Module-level singleton — import this throughout the codebase
settings = Settings()
