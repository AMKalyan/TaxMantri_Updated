"""
Business-rule checks on a UserFinancialProfile (AY 2026-27), run after
Pydantic validation: deduction caps and the 50L ITR-1 income limit.

HRA <= basic salary is checked by the schema's model_validator, so it isn't
repeated here.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from backend.agents.input_agent.schemas import AgeBracket, UserFinancialProfile

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Caps are repeated here rather than imported from tax_engine to avoid an
# import cycle.
# ---------------------------------------------------------------------------
_CAP_80C                   = 150_000
_CAP_80D_SELF_UNDER60      = 25_000
_CAP_80D_SELF_SENIOR       = 50_000          # age_bracket in (60_79, 80plus)
_CAP_80D_PARENTS_NON_SENIOR = 25_000         # parent_senior_citizen = False
_CAP_80D_PARENTS_SENIOR    = 50_000          # parent_senior_citizen = True
_CAP_24B                   = 200_000
_CAP_80CCD1B               = 50_000
_CAP_80CCD2_PCT            = 0.14            # new-regime cap; the engine applies 10% for the old regime
_ITR1_TOTAL_INCOME_MAX     = 5_000_000       # ITR-1 income limit


def validate_business_rules(profile: UserFinancialProfile) -> None:
    """
    Check the profile against the business rules, collecting every violation.

    Raises:
        ValueError: with a JSON list of {"field", "issue"} dicts, which the
            route turns into the standard error envelope.
    """
    violations: list[dict[str, Any]] = []

    # ---- 1. Section 80C cap ------------------------------------------------
    investments_80c = profile.investments_80c or 0.0
    if investments_80c > _CAP_80C:
        violations.append({
            "field": "investments_80c",
            "issue": (
                f"Value ₹{investments_80c:,.0f} exceeds the Section 80C maximum of "
                f"₹{_CAP_80C:,.0f}. Only ₹1,50,000 is deductible."
            ),
        })

    # ---- 2. Section 80D — self/family, age-dependent -----------------------
    health_self = profile.health_insurance_self or 0.0
    self_cap = (
        _CAP_80D_SELF_SENIOR
        if profile.age_bracket in (AgeBracket.sixty_79, AgeBracket.eighty_plus)
        else _CAP_80D_SELF_UNDER60
    )
    if health_self > self_cap:
        violations.append({
            "field": "health_insurance_self",
            "issue": (
                f"Value ₹{health_self:,.0f} exceeds the Section 80D self/family cap of "
                f"₹{self_cap:,.0f} for age bracket '{profile.age_bracket.value}'."
            ),
        })

    # ---- 3. Section 80D — parents, senior-citizen flag ---------------------
    health_parents = profile.health_insurance_parents or 0.0
    parent_cap = (
        _CAP_80D_PARENTS_SENIOR
        if profile.parent_senior_citizen
        else _CAP_80D_PARENTS_NON_SENIOR
    )
    if health_parents > parent_cap:
        violations.append({
            "field": "health_insurance_parents",
            "issue": (
                f"Value ₹{health_parents:,.0f} exceeds the Section 80D parents cap of "
                f"₹{parent_cap:,.0f} "
                f"({'senior citizen' if profile.parent_senior_citizen else 'non-senior'} parents)."
            ),
        })

    # ---- 4. Section 24(b) home loan interest cap ---------------------------
    home_loan_interest = profile.home_loan_interest or 0.0
    if home_loan_interest > _CAP_24B:
        violations.append({
            "field": "home_loan_interest",
            "issue": (
                f"Value ₹{home_loan_interest:,.0f} exceeds the Section 24(b) cap of "
                f"₹{_CAP_24B:,.0f}. Only ₹2,00,000 is deductible for a self-occupied property."
            ),
        })

    # ---- 5. Section 80CCD(1B) employee NPS cap -----------------------------
    employee_nps = profile.employee_nps_80ccd1b or 0.0
    if employee_nps > _CAP_80CCD1B:
        violations.append({
            "field": "employee_nps_80ccd1b",
            "issue": (
                f"Value ₹{employee_nps:,.0f} exceeds the Section 80CCD(1B) cap of "
                f"₹{_CAP_80CCD1B:,.0f}."
            ),
        })

    # ---- 6. Section 80CCD(2) employer NPS cap — 14% of basic_salary --------
    employer_nps = profile.employer_nps_80ccd2 or 0.0
    employer_nps_cap = _CAP_80CCD2_PCT * profile.basic_salary
    if employer_nps > employer_nps_cap:
        violations.append({
            "field": "employer_nps_80ccd2",
            "issue": (
                f"Value ₹{employer_nps:,.0f} exceeds the Section 80CCD(2) cap of "
                f"14% of basic salary = ₹{employer_nps_cap:,.0f}."
            ),
        })

    # ---- 7. ITR-1 eligibility: total income up to 50L ----------------------
    # Use the lower of the two regimes' taxable income; if even that is over
    # 50L the person has to file ITR-2 (and surcharge would apply).
    from backend.agents.evaluator_agent.tax_engine import (  # local import avoids cycles
        calculate_new_regime,
        calculate_old_regime,
    )
    total_income = min(
        calculate_old_regime(profile).taxable_income,
        calculate_new_regime(profile).taxable_income,
    )
    if total_income > _ITR1_TOTAL_INCOME_MAX:
        violations.append({
            "field": "other_income" if (profile.other_income or 0) > _ITR1_TOTAL_INCOME_MAX else "basic_salary",
            "issue": (
                f"Total income ₹{total_income:,.0f} exceeds ₹50,00,000. "
                "Taxpayers with total income above ₹50 lakh must file ITR-2, not ITR-1. "
                "TaxMantri only supports ITR-1 (Sahaj) filers."
            ),
        })

    if violations:
        # Log only IDs — never salary values, PAN or names.
        logger.info(
            "Business-rule validation failed: %d violation(s) profile_id=%s",
            len(violations),
            profile.profile_id,
        )
        raise ValueError(json.dumps(violations))


def validate_hra_consistency(
    profile: UserFinancialProfile,
    hra_declared: float | None,
) -> list[str]:
    """
    Compare our Rule 2A HRA exemption with the one declared in Form 16 line 2(e).

    Returns warning strings when they differ by more than 10%; an empty list if
    they agree, nothing was declared, or no HRA was received.
    """
    from backend.agents.input_agent.schemas import CityType

    warnings: list[str] = []

    if hra_declared is None:
        return warnings

    hra_received = profile.hra_received or 0.0
    if hra_received == 0:
        return warnings

    basic = profile.basic_salary
    annual_rent = (profile.monthly_rent_paid or 0.0) * 12
    metro_pct = 0.50 if profile.city_type == CityType.metro else 0.40

    rule_2a_exemption = min(
        hra_received,
        max(0.0, annual_rent - 0.10 * basic),
        metro_pct * basic,
    )

    if hra_declared > 0:
        relative_diff = abs(rule_2a_exemption - hra_declared) / hra_declared
    else:
        relative_diff = 1.0 if rule_2a_exemption > 0 else 0.0

    if relative_diff > 0.10:
        warnings.append(
            f"HRA exemption mismatch: Rule 2A computes ₹{rule_2a_exemption:,.0f} but "
            f"Form 16 declares ₹{hra_declared:,.0f}. "
            "Please verify your basic salary, monthly rent, and city type."
        )
        logger.info(
            "HRA consistency warning profile_id=%s rule2a=%.0f declared=%.0f",
            profile.profile_id,
            rule_2a_exemption,
            hra_declared,
        )

    return warnings
