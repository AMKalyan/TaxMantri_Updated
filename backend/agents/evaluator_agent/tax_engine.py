"""
Deterministic old/new regime tax calculator for FY 2025-26 (AY 2026-27).

Returns for FY 2025-26 are filed under the Income-tax Act, 1961; the
Income-tax Act, 2025 applies from tax year 2026-27. New-regime slabs follow
Budget 2025 (4L/8L/12L/16L/20L/24L breakpoints).
"""
from __future__ import annotations

from backend.agents.evaluator_agent.fmt import inr, round_tax

from backend.agents.input_agent.schemas import UserFinancialProfile
from backend.agents.evaluator_agent.schemas import (
    TaxResult, RegimeResult, DeductionBreakdown,
)

# ===========================================================================
# Assessment year
# ===========================================================================

ASSESSMENT_YEAR = "AY2026-27"

# ===========================================================================
# Old regime slab breakpoints (unchanged from AY 2024-25)
# ===========================================================================

OLD_SLAB_2_5L = 250_000
OLD_SLAB_5L   = 500_000
OLD_SLAB_10L  = 1_000_000

# ===========================================================================
# New regime slab breakpoints, revised in Budget 2025
# (the AY 2024-25 breakpoints were 3L/6L/9L/12L/15L).
# ===========================================================================

NEW_SLAB_4L  = 400_000
NEW_SLAB_8L  = 800_000
NEW_SLAB_12L = 1_200_000
NEW_SLAB_16L = 1_600_000
NEW_SLAB_20L = 2_000_000
NEW_SLAB_24L = 2_400_000

# ===========================================================================
# Deduction caps
# ===========================================================================

OLD_STD_DEDUCTION        = 50_000
NEW_STD_DEDUCTION        = 75_000

CAP_80C                  = 150_000

CAP_80D_SELF_UNDER60     = 25_000    # age_bracket == "under60"
CAP_80D_SELF_SENIOR      = 50_000    # age_bracket in ("60_79", "80plus")
CAP_80D_PARENTS_NON_SENIOR = 25_000  # parent_senior_citizen == False
CAP_80D_PARENTS_SENIOR   = 50_000    # parent_senior_citizen == True

CAP_80CCD1B              = 50_000    # Employee NPS — old regime only
# Employer NPS 80CCD(2) is allowed in both regimes.
# New regime cap 14% of salary (Finance (No.2) Act 2024); old regime 10% (non-government employer).
CAP_80CCD2_PCT_NEW       = 0.14
CAP_80CCD2_PCT_OLD       = 0.10

CAP_80TTA                = 10_000    # Savings interest — under60, old regime only
CAP_80TTB                = 50_000    # All interest — senior citizen, old regime only
CAP_24B                  = 200_000   # Home loan interest — old regime only

CESS_RATE                = 0.04

# ===========================================================================
# 87A rebate parameters, AY 2026-27
# ===========================================================================

OLD_87A_MAX_REBATE       = 12_500
OLD_87A_TAXABLE_CEILING  = 500_000

NEW_87A_MAX_REBATE       = 60_000
NEW_87A_TAXABLE_CEILING  = 1_200_000   # Effective ₹12L taxable income ceiling

# How the 87A rebate works for AY 2026-27:
#
# Old regime: if taxable income <= 5L, rebate = min(slab tax, 12,500), so tax
# is 0 up to 5L. Above 5L there is no rebate.
#
# New regime: if taxable income <= 12L, rebate = min(slab tax, 60,000), so tax
# is 0 up to 12L. Above 12L there is no rebate, but marginal relief caps the
# tax at the income in excess of 12L (taxable 12.1L -> tax 10,000, not 61,500).
# The relief stops mattering at roughly 12.7L taxable. With the 75K standard
# deduction, a gross salary of 12.75L ends up at zero tax.

# ===========================================================================
# Slab tables as (ceiling, rate) pairs
# ===========================================================================

OLD_REGIME_SLABS: list[tuple[float, float]] = [
    (250_000,      0.00),   # 0–2.5L: 0%
    (500_000,      0.05),   # 2.5–5L: 5%
    (1_000_000,    0.20),   # 5–10L: 20%
    (float("inf"), 0.30),   # >10L: 30%
]

# Senior citizens (60-79) and super seniors (80+) have higher old-regime
# basic exemption limits: ₹3,00,000 and ₹5,00,000. New-regime slabs are age-neutral.
OLD_REGIME_SLABS_SENIOR: list[tuple[float, float]] = [
    (300_000,      0.00),
    (500_000,      0.05),
    (1_000_000,    0.20),
    (float("inf"), 0.30),
]

OLD_REGIME_SLABS_SUPER_SENIOR: list[tuple[float, float]] = [
    (500_000,      0.00),
    (1_000_000,    0.20),
    (float("inf"), 0.30),
]


def _old_slabs_for(age_bracket) -> list[tuple[float, float]]:
    value = getattr(age_bracket, "value", age_bracket)
    if value == "80plus":
        return OLD_REGIME_SLABS_SUPER_SENIOR
    if value == "60_79":
        return OLD_REGIME_SLABS_SENIOR
    return OLD_REGIME_SLABS


NEW_REGIME_SLABS: list[tuple[float, float]] = [
    (400_000,      0.00),   # 0–4L: 0%
    (800_000,      0.05),   # 4–8L: 5%
    (1_200_000,    0.10),   # 8–12L: 10%
    (1_600_000,    0.15),   # 12–16L: 15%
    (2_000_000,    0.20),   # 16–20L: 20%
    (2_400_000,    0.25),   # 20–24L: 25%
    (float("inf"), 0.30),   # >24L: 30%
]


# ===========================================================================
# Internal helpers (pure functions)
# ===========================================================================

def _calculate_slab_tax(taxable_income: float, slabs: list[tuple[float, float]]) -> float:
    """Apply progressive slab rates to taxable_income."""
    tax = 0.0
    prev_ceiling = 0.0
    for ceiling, rate in slabs:
        if taxable_income <= prev_ceiling:
            break
        slab_income = min(taxable_income, ceiling) - prev_ceiling
        tax += slab_income * rate
        prev_ceiling = ceiling
    return tax


def calculate_hra_exemption(profile: UserFinancialProfile) -> float:
    """
    HRA exemption under Section 10(13A) / Rule 2A: the least of HRA received,
    50% (metro) or 40% of basic, and rent paid minus 10% of basic. The last
    term is clipped at 0 so low rent can't produce a negative exemption.
    Returns 0 if no HRA was received or no rent was paid.
    """
    if profile.hra_exemption_declared is not None and not profile.hra_received:
        # Form 16 path: trust the employer's Rule 2A computation (Part B 2(e)).
        return float(profile.hra_exemption_declared)
    hra = profile.hra_received or 0.0
    rent = profile.monthly_rent_paid or 0.0
    if hra == 0 or rent == 0:
        return 0.0
    metro_pct = 0.50 if profile.city_type == "metro" else 0.40
    annual_rent = rent * 12
    component_1 = hra
    component_2 = metro_pct * profile.basic_salary
    component_3 = max(0.0, annual_rent - 0.10 * profile.basic_salary)
    return min(component_1, component_2, component_3)


def _calculate_80d(profile: UserFinancialProfile) -> float:
    """80D deduction. Self and parent caps are independent; there is no combined cap."""
    self_cap   = CAP_80D_SELF_SENIOR if profile.age_bracket in ("60_79", "80plus") else CAP_80D_SELF_UNDER60
    parent_cap = CAP_80D_PARENTS_SENIOR if profile.parent_senior_citizen else CAP_80D_PARENTS_NON_SENIOR
    self_ded   = min(profile.health_insurance_self or 0.0, self_cap)
    parent_ded = min(profile.health_insurance_parents or 0.0, parent_cap)
    return self_ded + parent_ded


def _calculate_80tta_ttb_old(profile: UserFinancialProfile) -> float:
    """
    Old regime only: 80TTA (cap 10K) below 60, 80TTB (cap 50K) for seniors.
    Neither applies in the new regime.
    """
    amount = profile.savings_interest_80tta or 0.0
    if profile.age_bracket == "under60":
        return min(amount, CAP_80TTA)
    else:
        return min(amount, CAP_80TTB)


def _apply_87a_old(taxable_income: float, tax: float) -> float:
    """Old regime 87A: rebate up to 12,500 when taxable income is at most 5L."""
    if taxable_income <= OLD_87A_TAXABLE_CEILING:
        return max(0.0, tax - min(tax, OLD_87A_MAX_REBATE))
    return tax


def _apply_87a_new(taxable_income: float, tax: float) -> float:
    """
    New regime 87A rebate with marginal relief (Finance Act 2025).

    Up to 12L taxable the rebate wipes out the tax. Above 12L the tax is capped
    at the income over 12L: 12.1L -> 10,000; 13L -> 75,000 (relief no longer binds).
    """
    if taxable_income <= NEW_87A_TAXABLE_CEILING:
        return max(0.0, tax - min(tax, NEW_87A_MAX_REBATE))
    return min(tax, taxable_income - NEW_87A_TAXABLE_CEILING)


# ===========================================================================
# Old regime
# ===========================================================================

def calculate_old_regime(profile: UserFinancialProfile) -> RegimeResult:
    """
    Old regime tax for AY 2026-27.

    Allows the 50K standard deduction, HRA, LTA, 80C, 80D, 80CCD(1B),
    80CCD(2) up to 10% of salary, 80TTA/TTB, 24(b) and professional tax.
    """
    # HRA is part of gross income; the exemption is deducted separately.
    gross_income = (
        profile.basic_salary
        + (profile.hra_received or 0.0)
        + (profile.lta or 0.0)
        + (profile.special_allowance or 0.0)
        + (profile.other_allowances or 0.0)
        + (profile.other_income or 0.0)
    )

    ded_std      = float(OLD_STD_DEDUCTION)
    ded_hra      = calculate_hra_exemption(profile)
    ded_80c      = min(profile.investments_80c or 0.0, CAP_80C)
    ded_80d      = _calculate_80d(profile)
    ded_80ccd1b  = min(profile.employee_nps_80ccd1b or 0.0, CAP_80CCD1B)
    ded_80ccd2   = min(profile.employer_nps_80ccd2 or 0.0, CAP_80CCD2_PCT_OLD * profile.basic_salary)
    ded_80tta    = _calculate_80tta_ttb_old(profile)
    ded_24b      = min(profile.home_loan_interest or 0.0, CAP_24B)
    ded_pt       = profile.professional_tax or 0.0   # no cap here; the schema enforces the statutory max
    ded_lta      = float(profile.lta_exemption_declared or 0.0)   # Form 16 2(a); 0 for manual profiles

    total_deductions = (
        ded_std + ded_hra + ded_lta + ded_80c + ded_80d + ded_80ccd1b
        + ded_80ccd2 + ded_80tta + ded_24b + ded_pt
    )

    taxable_income = max(0.0, gross_income - total_deductions)
    slab_tax = _calculate_slab_tax(taxable_income, _old_slabs_for(profile.age_bracket))
    tax_after_87a = _apply_87a_old(taxable_income, slab_tax)

    # Cess is charged on the tax after the 87A rebate.
    cess = round(tax_after_87a * CESS_RATE, 2)
    total_tax = round_tax(tax_after_87a + cess)   # Section 288B

    return RegimeResult(
        gross_income=gross_income,
        total_deductions=total_deductions,
        taxable_income=taxable_income,
        tax_before_cess=round(tax_after_87a, 2),   # after 87A, before cess
        cess=cess,
        total_tax=total_tax,
        deduction_breakdown=DeductionBreakdown(
            standard_deduction=ded_std,
            hra_exemption=ded_hra,
            lta_exemption=ded_lta,
            section_80c=ded_80c,
            section_80d=ded_80d,
            section_80ccd1b=ded_80ccd1b,
            section_80ccd2=ded_80ccd2,
            section_80tta_ttb=ded_80tta,
            section_24b=ded_24b,
            professional_tax=ded_pt,
        ),
    )


# ===========================================================================
# New regime
# ===========================================================================

def calculate_new_regime(profile: UserFinancialProfile) -> RegimeResult:
    """
    New regime tax for AY 2026-27 (Section 115BAC).

    Only the 75K standard deduction and employer NPS 80CCD(2), capped at 14%
    of basic salary (Finance (No.2) Act 2024), are allowed.
    """
    gross_income = (
        profile.basic_salary
        + (profile.hra_received or 0.0)
        + (profile.lta or 0.0)
        + (profile.special_allowance or 0.0)
        + (profile.other_allowances or 0.0)
        + (profile.other_income or 0.0)
    )

    ded_std = float(NEW_STD_DEDUCTION)
    employer_nps_cap = CAP_80CCD2_PCT_NEW * profile.basic_salary
    ded_80ccd2 = min(profile.employer_nps_80ccd2 or 0.0, employer_nps_cap)

    total_deductions = ded_std + ded_80ccd2

    taxable_income = max(0.0, gross_income - total_deductions)
    slab_tax = _calculate_slab_tax(taxable_income, NEW_REGIME_SLABS)
    tax_after_87a = _apply_87a_new(taxable_income, slab_tax)

    # Cess is charged on the tax after the 87A rebate.
    cess = round(tax_after_87a * CESS_RATE, 2)
    total_tax = round_tax(tax_after_87a + cess)   # Section 288B

    return RegimeResult(
        gross_income=gross_income,
        total_deductions=total_deductions,
        taxable_income=taxable_income,
        tax_before_cess=round(tax_after_87a, 2),
        cess=cess,
        total_tax=total_tax,
        deduction_breakdown=DeductionBreakdown(
            standard_deduction=ded_std,
            section_80ccd2=ded_80ccd2,
            # other deductions don't apply in the new regime and stay at 0
        ),
    )


# ===========================================================================
# Regime comparison
# ===========================================================================

def compare_regimes(profile: UserFinancialProfile) -> TaxResult:
    """
    Compute both regimes and recommend the cheaper one, with a short rationale
    and optimisation suggestions. A tie goes to the new regime, the simpler option.
    """
    # Imported here because optimizer imports constants from this module.
    from backend.agents.evaluator_agent.optimizer import (
        generate_old_suggestions,
        generate_new_suggestions,
    )

    old = calculate_old_regime(profile)
    new = calculate_new_regime(profile)

    if old.total_tax < new.total_tax:
        recommended = "old"
        savings = new.total_tax - old.total_tax
    elif new.total_tax < old.total_tax:
        recommended = "new"
        savings = old.total_tax - new.total_tax
    else:
        recommended = "new"
        savings = 0.0

    if savings == 0.0:
        rationale = (
            f"Both regimes result in the same tax (₹{inr(old.total_tax)}). "
            "New Regime recommended as the simpler option with no mandatory investment requirements."
        )
    elif recommended == "old":
        # Name the main deductions behind the old-regime win.
        bd = old.deduction_breakdown
        key_deds: list[str] = []
        if bd.hra_exemption > 0:
            key_deds.append(f"HRA exemption ₹{inr(bd.hra_exemption)}")
        if bd.section_80c > 0:
            key_deds.append(f"80C ₹{inr(bd.section_80c)}")
        if bd.section_80d > 0:
            key_deds.append(f"80D ₹{inr(bd.section_80d)}")
        if bd.section_24b > 0:
            key_deds.append(f"Section 24(b) ₹{inr(bd.section_24b)}")
        top_deds = ", ".join(key_deds[:3]) if key_deds else "available deductions"
        rationale = (
            f"Old Regime saves ₹{inr(savings)} over the New Regime. "
            f"Old Regime tax: ₹{inr(old.total_tax)} vs New Regime tax: ₹{inr(new.total_tax)}. "
            f"Key deductions: {top_deds}."
        )
    else:
        rationale = (
            f"New Regime saves ₹{inr(savings)} over the Old Regime. "
            f"New Regime tax: ₹{inr(new.total_tax)} vs Old Regime tax: ₹{inr(old.total_tax)}. "
            f"Your total eligible Old Regime deductions (₹{inr(old.total_deductions)}) "
            f"are insufficient to overcome the lower New Regime slab rates."
        )

    old_suggestions = generate_old_suggestions(profile, old)
    new_suggestions = generate_new_suggestions(profile, new)

    return TaxResult(
        old_regime=old,
        new_regime=new,
        recommended_regime=recommended,
        savings_amount=round(savings, 2),
        rationale=rationale,
        old_regime_suggestions=old_suggestions,
        new_regime_suggestions=new_suggestions,
    )
