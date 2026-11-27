"""
Plain-English suggestions for unused deduction headroom (AY 2026-27).

This module imports constants from tax_engine, so tax_engine imports it
lazily inside compare_regimes() to avoid a cycle.
"""
from __future__ import annotations

from backend.agents.evaluator_agent.fmt import inr, round_tax

from backend.agents.input_agent.schemas import UserFinancialProfile
from backend.agents.evaluator_agent.schemas import RegimeResult
from backend.agents.evaluator_agent.tax_engine import (
    CAP_80C,
    CAP_80D_SELF_UNDER60, CAP_80D_SELF_SENIOR,
    CAP_80D_PARENTS_NON_SENIOR, CAP_80D_PARENTS_SENIOR,
    CAP_80CCD1B, CAP_24B, CAP_80CCD2_PCT_NEW,
)

_SUGGESTION_MIN_SAVING = 1_000   # Suppress suggestions where tax saving < ₹1,000
_MAX_SUGGESTIONS = 3


def _old_marginal_rate(taxable_income: float) -> float:
    """Old-regime marginal rate including cess (e.g. 0.312 in the 30% slab)."""
    if taxable_income > 1_000_000:    # > ₹10L: 30% slab
        return 0.30 * 1.04
    elif taxable_income > 500_000:    # > ₹5L: 20% slab
        return 0.20 * 1.04
    elif taxable_income > 250_000:    # > ₹2.5L: 5% slab
        return 0.05 * 1.04
    else:
        return 0.0   # Already in zero-tax bracket


def _new_marginal_rate(taxable_income: float) -> float:
    """New-regime marginal rate including cess."""
    if taxable_income > 2_400_000:    # > ₹24L: 30%
        return 0.30 * 1.04
    elif taxable_income > 2_000_000:  # > ₹20L: 25%
        return 0.25 * 1.04
    elif taxable_income > 1_600_000:  # > ₹16L: 20%
        return 0.20 * 1.04
    elif taxable_income > 1_200_000:  # > ₹12L: 15%
        return 0.15 * 1.04
    elif taxable_income > 800_000:    # > ₹8L: 10%
        return 0.10 * 1.04
    elif taxable_income > 400_000:    # > ₹4L: 5%
        return 0.05 * 1.04
    else:
        return 0.0


def generate_old_suggestions(
    profile: UserFinancialProfile,
    old_result: RegimeResult,
) -> list[str]:
    """
    Suggest unused old-regime headroom (80C, 80D, 80CCD(1B), 24(b)).
    Returns up to 3, largest saving first, skipping any saving under 1,000.
    """
    effective_rate = _old_marginal_rate(old_result.taxable_income)
    if effective_rate == 0.0:
        return []   # zero-tax bracket, nothing to save

    bd = old_result.deduction_breakdown

    # --- Collect candidates ---
    candidates: list[tuple[float, str]] = []   # (saving, suggestion_text)

    # 1. 80C headroom
    used_80c = bd.section_80c
    headroom_80c = CAP_80C - used_80c
    saving_80c = headroom_80c * effective_rate
    if headroom_80c > 0 and saving_80c >= _SUGGESTION_MIN_SAVING:
        candidates.append((
            saving_80c,
            f"Invest ₹{inr(headroom_80c)} more in 80C instruments (PPF, ELSS, LIC) "
            f"to save ₹{inr(round(saving_80c))} in the Old Regime.",
        ))

    # 2. 80D self headroom
    self_cap = CAP_80D_SELF_SENIOR if profile.age_bracket in ("60_79", "80plus") else CAP_80D_SELF_UNDER60
    used_self = min(profile.health_insurance_self or 0.0, self_cap)
    headroom_self = self_cap - used_self
    saving_self = headroom_self * effective_rate
    if headroom_self > 0 and saving_self >= _SUGGESTION_MIN_SAVING:
        candidates.append((
            saving_self,
            f"Pay ₹{inr(headroom_self)} more in health insurance (self/family) under Section 80D "
            f"to save ₹{inr(round(saving_self))} in the Old Regime.",
        ))

    # 3. 80D parents headroom
    parent_cap = CAP_80D_PARENTS_SENIOR if profile.parent_senior_citizen else CAP_80D_PARENTS_NON_SENIOR
    used_parents = min(profile.health_insurance_parents or 0.0, parent_cap)
    headroom_parents = parent_cap - used_parents
    saving_parents = headroom_parents * effective_rate
    if headroom_parents > 0 and saving_parents >= _SUGGESTION_MIN_SAVING:
        candidates.append((
            saving_parents,
            f"Pay ₹{inr(headroom_parents)} more in parent health insurance under Section 80D "
            f"to save ₹{inr(round(saving_parents))} in the Old Regime.",
        ))

    # 4. 80CCD(1B) employee NPS headroom
    used_nps = bd.section_80ccd1b
    headroom_nps = CAP_80CCD1B - used_nps
    saving_nps = headroom_nps * effective_rate
    if headroom_nps > 0 and saving_nps >= _SUGGESTION_MIN_SAVING:
        candidates.append((
            saving_nps,
            f"Contribute ₹{inr(headroom_nps)} more to NPS (Section 80CCD(1B)) "
            f"to save ₹{inr(round(saving_nps))} in the Old Regime.",
        ))

    # 5. Section 24(b) home loan interest headroom
    used_24b = bd.section_24b
    headroom_24b = CAP_24B - used_24b
    saving_24b = headroom_24b * effective_rate
    if headroom_24b > 0 and saving_24b >= _SUGGESTION_MIN_SAVING:
        candidates.append((
            saving_24b,
            f"Home loan interest paid up to ₹{inr(headroom_24b)} more can be claimed under "
            f"Section 24(b) to save ₹{inr(round(saving_24b))} in the Old Regime.",
        ))

    # Sort by saving descending, cap at 3
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [text for _, text in candidates[:_MAX_SUGGESTIONS]]


def generate_new_suggestions(
    profile: UserFinancialProfile,
    new_result: RegimeResult,
) -> list[str]:
    """
    Suggest new-regime headroom. Employer NPS 80CCD(2) is the only deduction
    that can be optimised; savings under 1,000 are skipped.
    """
    effective_rate = _new_marginal_rate(new_result.taxable_income)
    if effective_rate == 0.0:
        return []

    nps_cap = CAP_80CCD2_PCT_NEW * profile.basic_salary
    used_nps = new_result.deduction_breakdown.section_80ccd2
    headroom = nps_cap - used_nps
    saving = headroom * effective_rate

    if headroom > 0 and saving >= _SUGGESTION_MIN_SAVING:
        return [
            f"Ask your employer to contribute ₹{inr(headroom)} more to NPS (Section 80CCD(2)) "
            f"to save ₹{inr(round(saving))} in the New Regime."
        ]
    return []
