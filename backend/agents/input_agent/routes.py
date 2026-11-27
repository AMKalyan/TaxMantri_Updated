"""
Profile routes: POST /api/profile, GET /api/profile/{profile_id},
POST /api/upload and PUT /api/profile/confirm.

There is no user authentication. PAN, if present, is hashed before storage.
"""
from __future__ import annotations

import hashlib
import json
import logging
import magic
import os
import tempfile
import uuid
from typing import Any

from fastapi.concurrency import run_in_threadpool
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.input_agent.schemas import (
    ConfirmRequest,
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    UserFinancialProfile,
)
from backend.agents.input_agent.validator import validate_business_rules, validate_hra_consistency
from backend.config import settings
from backend.database import get_db
from backend.ratelimit import rate_limit
from backend.store import get_profile, save_profile

router = APIRouter(prefix="/api", tags=["input_agent"])
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Upload constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_SIZE = settings.max_upload_mb * 1024 * 1024
ALLOWED_MIMES = {"application/pdf", "image/jpeg", "image/png"}
MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
OCR_SESSION_TTL = 1800  # 30 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_pan_if_present(profile_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Return profile_dict with any 'pan' value replaced by its SHA-256 hex digest.

    The schema has no 'pan' field today; this keeps a plaintext PAN out of
    storage if one is ever added.
    """
    if "pan" in profile_dict and profile_dict["pan"]:
        plaintext = str(profile_dict["pan"])
        profile_dict = dict(profile_dict)          # don't mutate the caller's dict
        profile_dict["pan"] = hashlib.sha256(plaintext.encode()).hexdigest()
    return profile_dict


def _make_validation_error_response(violations_json: str) -> JSONResponse:
    """
    Parse the JSON-encoded violations list from validate_business_rules() and
    return a standard 422 ErrorResponse.
    """
    try:
        violations: list[dict[str, Any]] = json.loads(violations_json)
    except (json.JSONDecodeError, ValueError):
        # The message may be plain text, e.g. from a model_validator.
        violations = [{"field": None, "issue": violations_json}]

    details = [ErrorDetail(field=v.get("field"), issue=v["issue"]) for v in violations]
    body = ErrorResponse(
        error=ErrorBody(
            code="VALIDATION_ERROR",
            message="Profile validation failed",
            details=details,
        )
    )
    return JSONResponse(status_code=422, content=body.model_dump())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/profile", dependencies=[Depends(rate_limit("profile", per_minute=20, per_day=300))])
async def create_profile(
    profile: UserFinancialProfile,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Validate and save a profile.

    Returns 200 with {profile_id, session_id, status, validation_errors}, or 422
    listing every business-rule violation.
    """
    try:
        validate_business_rules(profile)
    except ValueError as e:
        return _make_validation_error_response(str(e))

    profile_dict = profile.model_dump()
    profile_dict = _hash_pan_if_present(profile_dict)
    profile = UserFinancialProfile.model_validate(profile_dict)

    session_id = str(uuid.uuid4())
    profile_id = await save_profile(db, profile, session_id=session_id)

    # Log only IDs — never salary values, PAN or names.
    logger.info(
        "Profile created profile_id=%s session_id=%s input_method=%s",
        profile_id,
        session_id,
        profile.input_method.value,
    )

    return JSONResponse(
        status_code=200,
        content={
            "profile_id": profile_id,
            "session_id": session_id,
            "status": "created",
            "validation_errors": [],
        },
    )


@router.get("/profile/{profile_id}")
async def get_profile_by_id(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return a stored profile, or 404 if it doesn't exist."""
    profile = await get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")

    logger.info("Profile retrieved profile_id=%s", profile_id)
    return JSONResponse(status_code=200, content=profile.model_dump())


# ---------------------------------------------------------------------------
# POST /api/upload
# ---------------------------------------------------------------------------

@router.post("/upload", dependencies=[Depends(rate_limit("upload", per_minute=5, per_day=50))])
async def upload_form16(
    background_tasks: BackgroundTasks,
    request: Request,
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Run OCR on an uploaded Form 16 (PDF or image) and return per-field
    confidence (green/yellow/red). The result is kept in Redis for 30 minutes
    for PUT /api/profile/confirm.

    Returns 422 FILE_TOO_LARGE or INVALID_MIME_TYPE without writing to disk.
    """
    # Validate size and type in memory before anything touches the disk.
    contents = await file.read()

    if len(contents) > MAX_UPLOAD_SIZE:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": f"File size exceeds maximum allowed {settings.max_upload_mb} MB",
                    "details": [],
                }
            },
        )

    # Sniff the type from the bytes; the client-supplied content_type can be spoofed.
    detected_mime = magic.from_buffer(contents[:2048], mime=True)
    if detected_mime not in ALLOWED_MIMES:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_MIME_TYPE",
                    "message": (
                        f"Unsupported file type '{detected_mime}'. "
                        "Allowed: PDF, JPEG, PNG"
                    ),
                    "details": [],
                }
            },
        )

    suffix = MIME_EXTENSIONS[detected_mime]
    temp_path = os.path.join(
        tempfile.gettempdir(),
        f"taxmantri_{uuid.uuid4().hex}{suffix}",
    )
    with open(temp_path, "wb") as fh:
        fh.write(contents)

    # Delete the temp file after the response is sent. Pass the path, not the
    # UploadFile, which may already be closed by then.
    background_tasks.add_task(os.unlink, temp_path)

    # OCR is CPU-bound, so run it in a worker thread.
    from backend.agents.input_agent.ocr_service import extract_form16  # lazy import
    result = await run_in_threadpool(extract_form16, temp_path)

    session_id = str(uuid.uuid4())
    redis = request.app.state.redis
    await redis.setex(
        f"ocr:{session_id}",
        OCR_SESSION_TTL,
        result.model_dump_json(),
    )

    logger.info(
        "Form16 uploaded session_id=%s green=%d yellow=%d red=%d",
        session_id,
        result.summary.green_count,
        result.summary.yellow_count,
        result.summary.red_count,
    )

    # reference_fields are Form 16 totals shown back to the user (e.g. the
    # declared HRA exemption). missing_profile_fields lists what Form 16 can't
    # provide; the frontend asks for these in the confirmation step.
    return JSONResponse(
        status_code=200,
        content={
            "session_id": session_id,
            "extracted_fields": {
                k: v.model_dump() for k, v in result.extracted_fields.items()
            },
            "reference_fields": result.reference_fields,
            "missing_profile_fields": result.missing_profile_fields,
            "summary": result.summary.model_dump(),
            "warnings": [w.model_dump() for w in result.warnings],
        },
    )


# ---------------------------------------------------------------------------
# PUT /api/profile/confirm
# ---------------------------------------------------------------------------

@router.put("/profile/confirm")
async def confirm_profile(
    body: ConfirmRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Merge OCR fields with the user's edits, validate, and save the profile.

    Returns 200 {profile_id, status, warnings}, 404 SESSION_NOT_FOUND, or
    422 VALIDATION_ERROR with field-level details.
    """
    redis = request.app.state.redis

    # Written by POST /api/upload with a 30-minute TTL.
    raw = await redis.get(f"ocr:{body.session_id}")
    if raw is None:
        # Return the 404 directly: the global HTTPException handler would turn
        # it into a generic NOT_FOUND, and the frontend expects SESSION_NOT_FOUND.
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "SESSION_NOT_FOUND",
                    "message": (
                        "OCR session expired or not found. "
                        "Please re-upload your Form 16."
                    ),
                    "details": [],
                }
            },
        )

    # profile_fields are the OCR values that map onto the profile;
    # reference_fields are Form 16 totals used for cross-checks only.
    ocr_data = json.loads(raw)
    base_fields: dict = ocr_data.get("profile_fields", {})
    reference_fields: dict = ocr_data.get("reference_fields", {})

    # User edits win over OCR values, and may include fields OCR can't read
    # (rent, city type, age bracket, ...).
    merged: dict = {**base_fields, **body.edited_fields}
    merged["input_method"] = "ocr"

    # basic_salary here is the gross 17(1) salary with HRA/LTA included, so
    # unless the user split out hra_received, use Form 16's declared exemptions.
    if not merged.get("hra_received") and reference_fields.get("hra_exempt_10_13a"):
        merged.setdefault("hra_exemption_declared", reference_fields["hra_exempt_10_13a"])
    if reference_fields.get("lta_exempt_10_5"):
        merged.setdefault("lta_exemption_declared", reference_fields["lta_exempt_10_5"])

    try:
        profile = UserFinancialProfile(**merged)
    except ValidationError as exc:
        details = [
            {
                "field": ".".join(str(loc) for loc in err["loc"]),
                "issue": err["msg"],
            }
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Profile validation failed",
                    "details": details,
                }
            },
        )

    # Same business rules as POST /api/profile; violations arrive as a JSON list.
    try:
        validate_business_rules(profile)
    except ValueError as exc:
        try:
            violations = json.loads(str(exc))
        except (json.JSONDecodeError, TypeError):
            violations = [{"field": "unknown", "issue": str(exc)}]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Profile validation failed",
                    "details": violations,
                }
            },
        )

    # Compare our Rule 2A figure with the employer's declared exemption
    # (Form 16 line 2(e)). Mismatches are warnings, not errors.
    hra_declared: float | None = reference_fields.get("hra_exempt_10_13a")
    hra_warnings = validate_hra_consistency(profile, hra_declared)

    profile_id = await save_profile(db, profile, session_id=body.session_id)

    logger.info(
        "OCR profile confirmed profile_id=%s session_id=%s hra_warnings=%d",
        profile_id,
        body.session_id,
        len(hra_warnings),
    )

    # The profile is saved even when there are warnings; the frontend shows
    # them and the user can go back and edit.
    return JSONResponse(
        status_code=200,
        content={
            "profile_id": profile_id,
            "status": "confirmed",
            "warnings": hra_warnings,
        },
    )
