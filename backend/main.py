"""
main.py — TaxMantri FastAPI application entry point.

Start with (from the repository root):
    uvicorn backend.main:app --reload --port 8000
"""
import logging
import os
import subprocess
import sys
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.config import settings

# ---------------------------------------------------------------------------
# Logging — configured before anything else
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — startup & shutdown hooks
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Run migrations and set up Redis, the retriever, the LLM client and the
    retention task on startup; close Redis on shutdown.
    """
    # --- 1. Database: run Alembic migrations ---
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=backend_dir,
    )
    if result.returncode != 0:
        logger.error("Alembic migration failed:\n%s", result.stderr)
        raise RuntimeError(f"Alembic migration failed: {result.stderr}")
    msg = result.stdout.strip() or "No pending migrations"
    logger.info("Alembic: %s", msg)

    # --- 2. Redis connection pool ---
    from backend.cache import create_redis_pool
    app.state.redis = await create_redis_pool()

    # --- 3. RAG retriever — loads the prebuilt index shipped with the app ---
    import asyncio
    from backend.agents.matcher_agent.retriever import TaxRetriever

    try:
        app.state.retriever = await asyncio.to_thread(TaxRetriever)
    except Exception as exc:  # missing index or missing API key
        logger.warning("RAG retriever unavailable — chat will return 503: %s", exc)
        app.state.retriever = None

    # --- 4. Gemini chat client ---
    from backend.llm import make_llm_client
    app.state.llm = make_llm_client()
    logger.info("Gemini model=%s ready=%s", settings.chat_model, app.state.llm is not None)

    # --- 5. Semaphore for LLM calls (created here because it needs a running loop) ---
    app.state.rag_semaphore = asyncio.Semaphore(2)
    logger.info("RAG semaphore initialized (concurrency=2)")

    # --- 6. Data retention: purge old user data now and hourly while awake ---
    from backend.privacy import retention_loop
    retention_task = asyncio.create_task(retention_loop())

    logger.info("TaxMantri v%s starting up", settings.app_version)
    yield
    retention_task.cancel()

    # --- Shutdown ---
    await app.state.redis.aclose()
    logger.info("Redis connection pool closed")
    logger.info("TaxMantri shutting down")



# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TaxMantri API",
    version=settings.app_version,
    description=(
        "GenAI-powered ITR-1 tax co-pilot for Indian salaried individuals. "
        "Compares Old vs New regime, identifies missed deductions, and guides ITR-1 filing."
    ),
    lifespan=lifespan,
    # Disable default /docs redirect on 422 — we handle validation errors ourselves
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS middleware — restricted to frontend origins from settings
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Error response helper
# ---------------------------------------------------------------------------
def _make_error_response(
    code: str,
    message: str,
    details: list[dict[str, Any]] | None = None,
    status_code: int = 500,
) -> JSONResponse:
    """Build a standard {error: {code, message, details}} response."""
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
        }
    }
    return JSONResponse(status_code=status_code, content=body)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return request validation errors in the standard envelope, all fields at once."""
    details = []
    for error in exc.errors():
        # Build dot-notation field path, excluding the top-level 'body' loc
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        details.append({"field": field or None, "issue": error["msg"]})
    return _make_error_response(
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=details,
        status_code=422,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Convert an HTTPException to the standard envelope with a named error code."""
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        413: "FILE_TOO_LARGE",
        415: "INVALID_MIME_TYPE",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    return _make_error_response(
        code=code,
        message=str(exc.detail),
        status_code=exc.status_code,
    )


@app.exception_handler(ValueError)
async def value_error_handler(
    request: Request, exc: ValueError
) -> JSONResponse:
    """Report a ValueError from business logic as a 422 VALIDATION_ERROR."""
    logger.info("ValueError on %s: %s", request.url.path, exc)
    return _make_error_response(
        code="VALIDATION_ERROR",
        message=str(exc) if settings.debug else "Invalid input data",
        status_code=422,
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """
    Catch-all for unexpected errors. The traceback is logged; the response
    includes the exception only when DEBUG is on.
    """
    logger.error(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=True,
    )
    if settings.debug:
        details = [{"issue": f"{type(exc).__name__}: {exc}"}]
        message = "An unexpected error occurred (debug details included)"
    else:
        details = []
        message = "An unexpected error occurred"
    return _make_error_response(
        code="INTERNAL_ERROR",
        message=message,
        details=details,
        status_code=500,
    )


# ---------------------------------------------------------------------------
# Health endpoint (no auth required)
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["System"])
async def health_check() -> dict:
    """Service health check."""
    return {
        "status": "ok",
        "version": settings.app_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }



# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
from backend.agents.input_agent.routes import router as input_agent_router
from backend.agents.evaluator_agent.routes import router as evaluator_agent_router
from backend.agents.matcher_agent.routes import router as matcher_agent_router

app.include_router(input_agent_router)
app.include_router(evaluator_agent_router)
app.include_router(matcher_agent_router)
from backend.agents.assistant.routes import router as assistant_router  # noqa: E402
app.include_router(assistant_router)
from backend.privacy import router as privacy_router  # noqa: E402
app.include_router(privacy_router)
