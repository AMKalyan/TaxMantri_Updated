"""
Golden-value checks for the FY 2025-26 / AY 2026-27 tax engine.

Expected totals are computed by hand from Finance Act 2025 rules:
  New regime slabs 0-4L 0% | 4-8L 5% | 8-12L 10% | 12-16L 15% | 16-20L 20% | 20-24L 25% | >24L 30%
  Old regime slabs 0-2.5L 0% | 2.5-5L 5% | 5-10L 20% | >10L 30%
  Std deduction ₹75k new / ₹50k old; 87A ₹60k up to ₹12L new (with marginal relief) / ₹12.5k up to ₹5L old
  80CCD(2) employer NPS: 14% of basic (new) / 10% (old); cess 4%.

Run: pytest backend/tests/test_tax_golden.py   (from the repository root)
"""
import pytest

from backend.agents.evaluator_agent.tax_engine import calculate_new_regime, calculate_old_regime
from backend.agents.input_agent.schemas import UserFinancialProfile


def _profile(**kw) -> UserFinancialProfile:
    base = dict(input_method="manual", city_type="metro", age_bracket="under60")
    base.update(kw)
    return UserFinancialProfile(**base)


NEW_CASES = [
    # (description, profile kwargs, expected taxable, expected total tax)
    ("₹12.75L salary → ₹12L taxable → zero tax", dict(basic_salary=1_275_000), 1_200_000, 0),
    ("₹12.1L taxable → marginal relief caps tax at ₹10k", dict(basic_salary=1_285_000), 1_210_000, 10_400),
    ("₹12.7L taxable → relief still binds (₹70k)", dict(basic_salary=1_345_000), 1_270_000, 72_800),
    ("₹13L taxable → relief no longer binds", dict(basic_salary=1_375_000), 1_300_000, 78_000),
    ("₹25L taxable → top slab", dict(basic_salary=2_575_000), 2_500_000, 343_200),
    ("Employer NPS 14% deductible in new regime", dict(basic_salary=1_000_000, employer_nps_80ccd2=140_000), 785_000, 0),
]

OLD_CASES = [
    ("80C + 80D, ₹7.75L taxable", dict(basic_salary=1_000_000, investments_80c=150_000, health_insurance_self=25_000), 775_000, 70_200),
    ("Taxable ≤ ₹5L → 87A rebate → zero", dict(basic_salary=550_000, investments_80c=50_000), 450_000, 0),
    ("Employer NPS capped at 10% in old regime", dict(basic_salary=1_000_000, employer_nps_80ccd2=140_000), 850_000, 85_800),
    ("Senior 60-79: ₹3L exemption, ₹7L taxable", dict(basic_salary=750_000, age_bracket="60_79"), 700_000, 52_000),
    ("Super senior 80+: ₹5L exemption, ₹7L taxable", dict(basic_salary=750_000, age_bracket="80plus"), 700_000, 41_600),
    ("HRA Rule 2A metro: min(3L, 3L, 2.4L) = 2.4L exempt",
     dict(basic_salary=600_000, hra_received=300_000, special_allowance=300_000, monthly_rent_paid=25_000), 910_000, 98_280),
    ("Form 16 path: gross ₹12L, declared HRA ₹2.4L + LTA ₹30k exempt",
     dict(basic_salary=1_200_000, input_method="ocr", hra_exemption_declared=240_000, lta_exemption_declared=30_000),
     880_000, 92_040),
    ("Sample profile: ₹1,39,651.20 rounded to ₹1,39,650 (Section 288B)",
     dict(basic_salary=900_000, hra_received=360_000, special_allowance=300_000, monthly_rent_paid=25_000,
          professional_tax=2_400, investments_80c=150_000, health_insurance_self=25_000, employee_nps_80ccd1b=50_000),
     1_072_600, 139_650),
]


@pytest.mark.parametrize("desc,kw,taxable,total", NEW_CASES, ids=[c[0] for c in NEW_CASES])
def test_new_regime(desc, kw, taxable, total):
    r = calculate_new_regime(_profile(**kw))
    assert r.taxable_income == pytest.approx(taxable)
    assert r.total_tax == pytest.approx(total)


@pytest.mark.parametrize("desc,kw,taxable,total", OLD_CASES, ids=[c[0] for c in OLD_CASES])
def test_old_regime(desc, kw, taxable, total):
    r = calculate_old_regime(_profile(**kw))
    assert r.taxable_income == pytest.approx(taxable)
    assert r.total_tax == pytest.approx(total)
