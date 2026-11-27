"""
Calculation routes: POST /api/calculate, GET /api/itr1-mapping/{profile_id}
and GET /api/export/{profile_id}.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import ValidationError

from backend.agents.evaluator_agent.explain import calculate_with_explanation
from backend.agents.evaluator_agent.itr1_mapper import build_itr1_mapping
from backend.agents.evaluator_agent.pdf_generator import generate_tax_report
from backend.agents.evaluator_agent.tax_engine import compare_regimes
from backend.agents.evaluator_agent.schemas import TaxResult
from backend.agents.input_agent.schemas import (
    ErrorBody,
    ErrorDetail,
    ErrorResponse,
    UserFinancialProfile,
)
from backend.agents.input_agent.validator import validate_business_rules
from backend.database import get_db
from backend.ratelimit import rate_limit
from backend.store import get_profile, get_result, save_profile, save_result

router = APIRouter(prefix="/api", tags=["evaluator_agent"])
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_validation_error_response(violations_json: str) -> JSONResponse:
    """Parse JSON-encoded violations and return standard 422 error envelope."""
    try:
        violations: list[dict] = json.loads(violations_json)
    except (json.JSONDecodeError, ValueError):
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

@router.post("/calculate", dependencies=[Depends(rate_limit("calculate", per_minute=20, per_day=300, global_bucket="llm"))])
async def calculate_tax(
    request: Request,
    request_body: dict,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Calculate tax for either a full profile in the body (shape A) or
    {"profile_id": ...} referring to a stored one (shape B). See explain.py.
    """
    keys = set(request_body.keys())

    if keys == {"profile_id"}:
        # ----------------------------------------------------------------
        # Shape B — load stored confirmed profile
        # ----------------------------------------------------------------
        profile_id = request_body["profile_id"]
        profile = await get_profile(db, profile_id)
        if profile is None:
            raise HTTPException(
                status_code=404,
                detail=f"Profile '{profile_id}' not found",
            )

    else:
        # ----------------------------------------------------------------
        # Shape A — inline UserFinancialProfile body
        # ----------------------------------------------------------------
        try:
            profile = UserFinancialProfile.model_validate(request_body)
        except ValidationError as exc:
            details = [
                {"field": ".".join(str(x) for x in e["loc"]), "issue": e["msg"]}
                for e in exc.errors()
            ]
            return JSONResponse(
                status_code=422,
                content={"error": {"code": "VALIDATION_ERROR", "message": "Profile validation failed", "details": details}},
            )

        try:
            validate_business_rules(profile)
        except ValueError as exc:
            return _make_validation_error_response(str(exc))

        profile_id = profile.profile_id
        await save_profile(db, profile)

    # ---- Engine → retrieval → explanation -----------------------------------
    result = await calculate_with_explanation(request.app.state, profile)
    result = result.model_copy(update={"profile_id": profile_id})

    # ---- Persist TaxResult to PostgreSQL ------------------------------------
    await save_result(db, result)

    logger.info(
        "Tax calculated profile_id=%s recommended=%s savings=%s citations=%d",
        profile_id,
        result.recommended_regime,
        result.savings_amount,
        len(result.citations),
    )

    return JSONResponse(status_code=200, content=result.model_dump())


# ---------------------------------------------------------------------------
# GET /api/itr1-mapping/{profile_id}
# ---------------------------------------------------------------------------

@router.get("/itr1-mapping/{profile_id}")
async def get_itr1_mapping(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Return structured ITR-1 Sahaj field mapping for a calculated TaxResult."""
    profile = await get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")

    tax_result = await get_result(db, profile_id)
    if tax_result is None:
        raise HTTPException(
            status_code=404,
            detail="No tax calculation found for this profile. Call POST /api/calculate first.",
        )

    mapping = build_itr1_mapping(profile, tax_result)
    logger.info("ITR1 mapping returned profile_id=%s entries=%d", profile_id, len(mapping))
    return JSONResponse(status_code=200, content=[entry.model_dump() for entry in mapping])


# ---------------------------------------------------------------------------
# GET /api/export/{profile_id}
# ---------------------------------------------------------------------------

@router.get("/export/{profile_id}", dependencies=[Depends(rate_limit("export", per_minute=10, per_day=100))])
async def export_pdf(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Generate and download a formatted TaxMantri PDF report."""
    profile = await get_profile(db, profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile '{profile_id}' not found")

    tax_result = await get_result(db, profile_id)
    if tax_result is None:
        raise HTTPException(
            status_code=404,
            detail="No tax calculation found for this profile. Call POST /api/calculate first.",
        )

    buffer = generate_tax_report(profile, tax_result)
    filename = f"taxmantri_AY2026-27_{profile_id}.pdf"
    logger.info("PDF exported profile_id=%s filename=%s", profile_id, filename)

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
