"""
End-to-end check: Form 16 PDF → OCR extraction → confirm-route merge → tax engine.

For old-regime Form 16s, the engine's taxable income must equal the Form 16's own
"Total taxable income" line, i.e. no salary component is double-counted and the
employer-declared HRA/LTA exemptions are honoured.
"""
import random

import pytest

from backend.agents.evaluator_agent.tax_engine import calculate_old_regime
from backend.agents.input_agent.ocr_service import extract_form16
from backend.agents.input_agent.schemas import UserFinancialProfile
from eval.form16_gen import make_profile, render


def _merge_like_confirm_route(ocr, edited: dict) -> dict:
    """Mirror of PUT /api/profile/confirm steps 3-4b."""
    merged = {**ocr.profile_fields, **edited, "input_method": "ocr"}
    ref = ocr.reference_fields
    if not merged.get("hra_received") and ref.get("hra_exempt_10_13a"):
        merged.setdefault("hra_exemption_declared", ref["hra_exempt_10_13a"])
    if ref.get("lta_exempt_10_5"):
        merged.setdefault("lta_exemption_declared", ref["lta_exempt_10_5"])
    return merged


def _old_regime_samples(n=12, seed=7):
    rng = random.Random(seed)
    out = []
    i = 0
    while len(out) < n:
        i += 1
        p = make_profile(rng, i)
        if p["regime"] == "old" and p["hra_exempt_10_13a"] > 0:
            out.append((p, rng.random()))
    return out


@pytest.mark.parametrize("sample,_", _old_regime_samples())
def test_taxable_income_matches_form16(tmp_path, sample, _):
    pdf = tmp_path / f"{sample['id']}.pdf"
    render(sample, pdf, random.Random(1))
    ocr = extract_form16(str(pdf))
    merged = _merge_like_confirm_route(
        ocr, {"monthly_rent_paid": 30_000, "city_type": "metro", "age_bracket": "under60"}
    )
    profile = UserFinancialProfile(**merged)
    result = calculate_old_regime(profile)
    assert result.gross_income == pytest.approx(sample["gross_salary_17_1"])
    assert result.taxable_income == pytest.approx(sample["total_taxable_income"])
