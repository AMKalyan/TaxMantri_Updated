"""
Input schemas: UserFinancialProfile (used by every agent), the OCR result
models, and the shared error envelope.

Field names are part of the API contract with the frontend, so renaming one
is a breaking change.
"""
import uuid
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CityType(str, Enum):
    metro = "metro"
    non_metro = "non_metro"


class AgeBracket(str, Enum):
    under60 = "under60"
    sixty_79 = "60_79"
    eighty_plus = "80plus"


class InputMethod(str, Enum):
    ocr = "ocr"
    manual = "manual"


# ---------------------------------------------------------------------------
# UserFinancialProfile — central data contract
# ---------------------------------------------------------------------------

class UserFinancialProfile(BaseModel):
    """
    Financial profile of a salaried ITR-1 filer for AY 2026-27.

    Amounts are in INR and annual, except monthly_rent_paid. Unknown fields
    are rejected with a 422.
    """
    model_config = ConfigDict(extra="forbid")

    # --- Identity ---
    # Generated if omitted; a client may send one to upsert the same profile.
    profile_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID identifying this profile. Auto-generated if omitted.",
    )

    # --- Required annual income fields ---
    basic_salary: float = Field(
        ..., ge=0,
        description="Annual basic salary in INR (gross, before deductions).",
    )

    # --- Optional salary components ---
    hra_received: Optional[float] = Field(
        default=0, ge=0,
        description="Annual HRA component received from employer (CTC component, not HRA exemption).",
    )
    other_allowances: Optional[float] = Field(
        default=0, ge=0,
        description="Annual other allowances combined if not itemised separately.",
    )
    professional_tax: Optional[float] = Field(
        default=0, ge=0, le=2500,
        description="Annual professional tax deducted by employer. Constitutional max ₹2,500/year (Article 276).",
    )
    lta: Optional[float] = Field(
        default=0, ge=0,
        description="Leave Travel Allowance — annual.",
    )
    special_allowance: Optional[float] = Field(
        default=0, ge=0,
        description="Special/performance allowance — annual.",
    )

    # --- HRA calculation inputs ---
    monthly_rent_paid: Optional[float] = Field(
        default=0, ge=0,
        description=(
            "Monthly rent paid by taxpayer. "
            "Backend multiplies ×12 to get annual rent for HRA Rule 2A calculation. "
            "Set 0 if not paying rent."
        ),
    )
    city_type: CityType = Field(
        ...,
        description="Determines HRA metro percentage: metro=50% of basic, non_metro=40% of basic.",
    )

    # --- Other income (annual) ---
    other_income: Optional[float] = Field(
        default=0, ge=0,
        description="Income from other sources (interest, FD, freelance, etc.) — annual.",
    )

    # --- Chapter VI-A deductions (annual, all optional, default 0) ---
    investments_80c: Optional[float] = Field(
        default=0, ge=0,
        description=(
            "Total Section 80C investments: ELSS, PPF, LIC, EPF employee contribution, "
            "NSC, home loan principal repayment, tuition fees, etc. "
            "Tax engine caps at ₹1,50,000 internally."
        ),
    )
    ppf_contribution: Optional[float] = Field(
        default=0, ge=0,
        description="PPF contribution — informational breakdown of investments_80c.",
    )
    home_loan_principal: Optional[float] = Field(
        default=0, ge=0,
        description="Home loan principal repayment — informational breakdown of investments_80c.",
    )
    health_insurance_self: Optional[float] = Field(
        default=0, ge=0,
        description=(
            "Section 80D — health insurance premium for self, spouse, and children. "
            "Under 60: capped at ₹25,000. 60+: capped at ₹50,000."
        ),
    )
    health_insurance_parents: Optional[float] = Field(
        default=0, ge=0,
        description=(
            "Section 80D — health insurance premium for parents. "
            "If parents under 60: cap ₹25,000. If parents 60+: cap ₹50,000."
        ),
    )
    employee_nps_80ccd1b: Optional[float] = Field(
        default=0, ge=0,
        description=(
            "Employee voluntary NPS contribution under Section 80CCD(1B). "
            "Additional deduction of up to ₹50,000 — old regime ONLY. "
            "NOT allowed in new regime (tax engine ignores it for new regime)."
        ),
    )
    employer_nps_80ccd2: Optional[float] = Field(
        default=0, ge=0,
        description=(
            "Employer NPS contribution under Section 80CCD(2). "
            "Allowed in both regimes: up to 14% of basic_salary in the new regime, "
            "10% in the old regime."
        ),
    )
    home_loan_interest: Optional[float] = Field(
        default=0, ge=0,
        description=(
            "Section 24(b) — home loan interest for self-occupied property. "
            "Old regime cap: ₹2,00,000. NOT allowed in new regime."
        ),
    )
    savings_interest_80tta: Optional[float] = Field(
        default=0, ge=0,
        description=(
            "Section 80TTA (under 60) / 80TTB (60+) — deposit interest, old regime only. "
            "Under 60: 80TTA cap ₹10,000 (savings account only). "
            "60+: 80TTB cap ₹50,000 (savings + FD interest)."
        ),
    )

    # --- Profile metadata ---
    age_bracket: AgeBracket = Field(
        ...,
        description="Taxpayer age bracket — determines 80D limits, 87A eligibility, and senior citizen slabs.",
    )
    input_method: InputMethod = Field(
        ...,
        description="How this profile was created: 'ocr' (from Form 16) or 'manual' (wizard).",
    )

    # --- Parent age, for the 80D parent cap ---
    parent_senior_citizen: bool = Field(
        default=False,
        description=(
            "True if one or both parents are senior citizens (60+). "
            "False → 80D parent cap ₹25,000. True → cap ₹50,000."
        ),
    )

    # --- Form 16 employer-declared exemptions (OCR path only) ---
    # For a Form 16 profile, basic_salary holds the gross 17(1) salary with HRA
    # and LTA included, and the split is unknown, so the employer's declared
    # exempt amounts from Part B line 2 are used instead.
    hra_exemption_declared: Optional[float] = Field(
        default=None, ge=0,
        description="HRA exempt u/s 10(13A) as declared in Form 16 Part B 2(e). Old regime only.",
    )
    lta_exemption_declared: Optional[float] = Field(
        default=None, ge=0,
        description="LTA exempt u/s 10(5) as declared in Form 16 Part B 2(a). Old regime only.",
    )

    # --- Cross-field validation ---
    @model_validator(mode="after")
    def validate_hra_not_exceeds_basic(self) -> "UserFinancialProfile":
        """HRA component from employer cannot exceed basic salary."""
        hra = self.hra_received or 0
        if hra > self.basic_salary:
            raise ValueError(
                f"hra_received (₹{hra:,.0f}) cannot exceed "
                f"basic_salary (₹{self.basic_salary:,.0f})"
            )
        return self


# ---------------------------------------------------------------------------
# Error response models, used by the exception handlers in main.py
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    """Single field-level validation or business-rule error."""
    model_config = ConfigDict(extra="forbid")

    field: Optional[str] = None   # Dot-notation field path, e.g. "investments_80c"
    issue: str                     # Human-readable description of the problem


class ErrorBody(BaseModel):
    """Error envelope body."""
    model_config = ConfigDict(extra="forbid")

    code: str                                      # VALIDATION_ERROR, NOT_FOUND, etc.
    message: str                                   # High-level error description
    details: List[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Error envelope for all endpoints: {"error": {"code", "message", "details"}}."""
    model_config = ConfigDict(extra="forbid")

    error: ErrorBody


# ---------------------------------------------------------------------------
# OCR schemas
# ---------------------------------------------------------------------------

class FieldResult(BaseModel):
    """Per-field OCR extraction result. value is None if regex found no match."""
    value: Optional[float] = None
    confidence: Literal["green", "yellow", "red"]


class OCRSummary(BaseModel):
    """Summary counts of confidence levels across all extracted fields."""
    field_count: int
    green_count: int
    yellow_count: int
    red_count: int


class OCRWarning(BaseModel):
    """Non-fatal warning from OCR extraction (e.g. wrong assessment year)."""
    code: str
    message: str


class OCRResult(BaseModel):
    """
    Result of extract_form16().

    extracted_fields: every profile field OCR attempted, with confidence.
    profile_fields: the extracted fields that have a value; the confirm route
        merges user edits on top of these.
    reference_fields: Form 16 totals for display and cross-checks; not stored
        on the profile.
    missing_profile_fields: profile fields Form 16 can't supply (rent, city
        type, age bracket), which the user fills in at confirmation.
    """
    extracted_fields: dict[str, FieldResult]
    profile_fields: dict[str, float]
    reference_fields: dict[str, Optional[float]]
    missing_profile_fields: List[str] = Field(default_factory=list)
    summary: OCRSummary
    warnings: List[OCRWarning]


class ConfirmRequest(BaseModel):
    """
    Body for PUT /api/profile/confirm. edited_fields may hold any profile field,
    including ones OCR can't read from Form 16.
    """
    model_config = ConfigDict(extra="forbid")

    session_id: str
    edited_fields: dict = {}


__all__ = [
    "CityType",
    "AgeBracket",
    "InputMethod",
    "UserFinancialProfile",
    "ErrorDetail",
    "ErrorBody",
    "ErrorResponse",
    "FieldResult",
    "OCRSummary",
    "OCRWarning",
    "OCRResult",
    "ConfirmRequest",
]
