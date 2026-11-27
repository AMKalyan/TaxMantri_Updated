"""
Result schemas for the tax engine (AY 2026-27): per-regime results, the
regime comparison, and ITR-1 field mappings.
"""
from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# DeductionBreakdown — itemised deductions applied in one regime
# ---------------------------------------------------------------------------

class DeductionBreakdown(BaseModel):
    """
    Deductions actually applied in one regime, after caps (an 80C input of
    2L shows as 1.5L). In the new regime only standard_deduction and
    section_80ccd2 can be non-zero.
    """
    model_config = ConfigDict(extra="forbid")

    standard_deduction: float = 0         # ₹50K old / ₹75K new
    hra_exemption: float = 0              # Rule 2A min-of-3 — old regime only
    lta_exemption: float = 0              # Section 10(5) as declared in Form 16 — old regime only
    section_80c: float = 0               # Cap ₹1,50,000 — old regime only
    section_80d: float = 0               # 80D self + parents combined — old regime only
    section_80ccd1b: float = 0           # Employee NPS, cap ₹50K — old regime only
    section_80ccd2: float = 0            # Employer NPS, both regimes (cap 14% new / 10% old)
    section_80tta_ttb: float = 0         # 80TTA/80TTB — old regime only
    section_24b: float = 0               # Home loan interest, cap ₹2L — old regime only
    professional_tax: float = 0          # Section 16 — old regime only


# ---------------------------------------------------------------------------
# RegimeResult — full tax calculation for one regime
# ---------------------------------------------------------------------------

class RegimeResult(BaseModel):
    """
    Tax computation for one regime.

    tax_before_cess is the slab tax after the 87A rebate; cess is 4% of that
    (not of the pre-rebate tax), and total_tax is the sum of the two.
    """
    model_config = ConfigDict(extra="forbid")

    gross_income: float
    total_deductions: float
    taxable_income: float
    tax_before_cess: float       # After 87A rebate, before 4% cess
    cess: float                  # 4% of tax_before_cess
    total_tax: float             # tax_before_cess + cess (final payable amount)
    deduction_breakdown: DeductionBreakdown


# ---------------------------------------------------------------------------
# TaxResult — regime comparison output (public API of tax engine)
# ---------------------------------------------------------------------------

class TaxResult(BaseModel):
    """
    Output of compare_regimes(): both regime results, the recommendation,
    savings, rationale and per-regime suggestions.

    citations and law_context are filled in from retrieved law when available
    and stay empty for direct calls.
    """
    model_config = ConfigDict(extra="ignore")   # tolerate extra fields added by callers

    profile_id: Optional[str] = None     # Set by caller after persisting to DB

    old_regime: RegimeResult
    new_regime: RegimeResult

    recommended_regime: str              # "old" | "new"
    savings_amount: float                # abs(old_tax - new_tax)
    rationale: str                       # LLM-grounded rationale (EvaluatorAgent).

    # Kept separate so the frontend can show them under each regime.
    old_regime_suggestions: List[str] = []   # Up to 3, sorted by saving desc
    new_regime_suggestions: List[str] = []   # Up to 3, sorted by saving desc

    citations: List[dict] = []           # [{section, excerpt}] from MatcherAgent
    law_context: str = ""               # Synthesized IT Act context from MatcherAgent


# ---------------------------------------------------------------------------
# ITR1FieldMap — ITR-1 schedule field mapping
# ---------------------------------------------------------------------------

class ITR1FieldMap(BaseModel):
    """Maps a computed financial value to a specific ITR-1 form field."""
    model_config = ConfigDict(extra="forbid")

    itr1_field: str      # e.g. "Schedule S – Salary"
    schedule: str        # e.g. "Schedule S", "Part B-TI"
    value: float
    source_field: str    # Source UserFinancialProfile field, e.g. "basic_salary"
    regime: Literal["old", "new"]    # Which regime this entry belongs to
    note: Optional[str] = None       # Rule 2A breakdown for HRA; None for all other fields


__all__ = [
    "DeductionBreakdown",
    "RegimeResult",
    "TaxResult",
    "ITR1FieldMap",
]
