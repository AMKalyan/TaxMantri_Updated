"""
Form 16 field extraction. Entry point: extract_form16(file_path) -> OCRResult.

The upload route only handles I/O; everything here is plain functions that
can be tested without HTTP. The label patterns cover the common payroll
exports but other layouts may need new variants.

pytesseract, pdf2image and PIL are imported lazily so the app still starts
when Tesseract isn't installed.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Confidence thresholds
# ---------------------------------------------------------------------------

HIGH_CONFIDENCE = 0.90    # Full regex match on known label + numeric pattern → green
MEDIUM_CONFIDENCE = 0.70  # Fuzzy/fallback label match → yellow (currently unused)
NO_MATCH_CONFIDENCE = 0.0 # No regex match at all → red, value = None

# green > 0.85, yellow 0.60–0.85, red < 0.60
_THRESHOLD_GREEN = 0.85
_THRESHOLD_YELLOW = 0.60

# ---------------------------------------------------------------------------
# Tesseract config
# ---------------------------------------------------------------------------

OCR_CONFIG = "--oem 3 --psm 6"

# ---------------------------------------------------------------------------
# Field groupings
# ---------------------------------------------------------------------------

# Fields read from Form 16 that map 1:1 onto UserFinancialProfile. They go into
# extracted_fields, and into profile_fields when a value was found.
PROFILE_FIELDS = [
    "basic_salary",          # Form 16 Part B line 1(d) — gross salary per sec 17(1)
    "professional_tax",       # Form 16 Part B line 4(c)
    "investments_80c",        # Form 16 Part B line 10(d) deductible amount
    "health_insurance_self",  # Form 16 Part B line 10(g)
    "employee_nps_80ccd1b",   # Form 16 Part B line 10(e)
    "employer_nps_80ccd2",    # Form 16 Part B line 10(f)
    "home_loan_interest",     # Form 16 Part B line 7(a) — abs() applied on negative
    "savings_interest_80tta", # Form 16 Part B line 10(l)
]

# Fields read from Form 16 for display and cross-checks only; not stored on
# the profile.
#
# gross_salary_17_1  : Form 16 Part B line 1(d) — sum of all salary components.
#                      Can't be split into basic/HRA/LTA without the payslip.
# hra_exempt_10_13a  : Form 16 Part B line 2(e) — employer-declared HRA exemption,
#                      checked against our Rule 2A figure once the user enters
#                      basic salary, HRA and rent.
# lta_exempt_10_5    : Form 16 Part B line 2(a) — employer-declared LTA exemption.
# gross_total_income : Form 16 Part B line 9 — display/reconciliation only.
# tds_deducted       : Form 16 Part A total — display/reconciliation only.
REFERENCE_FIELDS = [
    "gross_salary_17_1",
    "hra_exempt_10_13a",
    "lta_exempt_10_5",
    "gross_total_income",
    "tds_deducted",
]

# Profile fields Form 16 doesn't contain. Returned as missing_profile_fields so
# the frontend can ask for them in the confirmation step.
NON_EXTRACTABLE_FIELDS = [
    "hra_received",           # Only exempt portion shown (line 2e), not amount received
    "lta",                    # Only exempt portion shown (line 2a), not amount received
    "special_allowance",      # Collapsed into gross salary line 1(d)
    "other_allowances",       # Collapsed into gross salary line 1(d)
    "monthly_rent_paid",      # Personal information — not in any tax document
    "city_type",              # Personal information — not in any tax document
    "age_bracket",            # Personal information — not in any tax document
    "parent_senior_citizen",  # Personal information — not in any tax document
]

# ---------------------------------------------------------------------------
# Two-column deduction fields
# ---------------------------------------------------------------------------
# Chapter VI-A rows have a gross and a deductible column:
#   row (d): "Total deduction u/s 80C  Rs. NIL  Rs. 1,30,000"
#   row (e): "80CCD (1B)               Rs. 1,30,000  Rs. 50,000"
# The first number on the line is the gross amount, so for these fields the
# last number (the deductible amount) is taken instead.
_TAIL_NUMBER_FIELDS: frozenset = frozenset({
    "investments_80c",        # row (d): total deductible u/s 80C+80CCC+80CCD(1)
    "employee_nps_80ccd1b",   # row (e): deductible u/s 80CCD(1B)
    "employer_nps_80ccd2",    # row (f2): deductible u/s 80CCD(2)
    "health_insurance_self",  # row (f): deductible u/s 80D
    "savings_interest_80tta", # row with 80TTA/80TTB
})


# ---------------------------------------------------------------------------
# Regex patterns — all fields
# ---------------------------------------------------------------------------

FIELD_PATTERNS: dict[str, re.Pattern] = {
    # ------------------------------------------------------------------ #
    # Profile fields                                                      #
    # ------------------------------------------------------------------ #

    # Form 16 Part B line 1(d): "Salary as per provisions contained in sec. 17(1)"
    # The gross salary is used as basic salary. The pattern looks up to 150
    # chars ahead, across newlines, because pdfplumber often puts the label
    # and the amount on separate lines.
    "basic_salary": re.compile(
        r"(?:"
        r"Salary\s+as\s+per\s+provisions\s+contained\s+in\s+sec(?:tion)?\.?\s*17\s*\(?1\)?"
        r"|Gross\s+Salary"
        r"|Total\s+(?:Gross\s+)?Earnings"
        r"|Total\s+Salary"
        r")",
        re.IGNORECASE,
    ),

    # Form 16 Part B line 4(c): "Tax on employment under section 16(iii)"
    # Also present as: "Professional Tax", "Prof. Tax", "Profession Tax"
    "professional_tax": re.compile(
        r"(?:"
        r"Tax\s+on\s+[Ee]mployment"
        r"|Professional\s+Tax"
        r"|Profession\s+Tax"
        r"|Prof\.?\s*Tax"
        r"|Entertainment\s+allowance\s+and\s+[Tt]ax\s+on\s+[Ee]mployment"
        r")",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 10(d): "Total deduction under section 80C, 80CCC and 80CCD(1)"
    # Also: "Gross amount" or "Deductible amount" under 80C section heading
    "investments_80c": re.compile(
        r"(?:"
        r"Total\s+deduction\s+under\s+section\s+80C"
        r"|(?:Gross|Deductible)\s+amount[^\n]{0,30}80C"
        r"|80C[^\n]{0,30}(?:Gross|Deductible|Total)\s+amount"
        r"|Deduction\s+in\s+respect\s+of\s+life\s+insurance"
        r"|Section\s+80C"
        r"|80\s*C\b"
        r")",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 10(g): "Deduction in respect of health insurance premia under section 80D"
    # Also: "Medical Insurance Premia u/s 80D", "Mediclaim", "80D"
    "health_insurance_self": re.compile(
        r"(?:"
        r"health\s+insurance\s+premi"
        r"|Medical\s+Insurance\s+Premi"
        r"|Mediclaim"
        r"|80\s*D\b"
        r"|Deduction[^\n]{0,30}80D"
        r")",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 10(e): section 80CCD(1B) — employee NPS contribution
    "employee_nps_80ccd1b": re.compile(
        r"(?:"
        r"80\s*CCD\s*[\(\[]?\s*1B\s*[\)\]]?"
        r"|notified\s+pension\s+scheme"
        r"|NPS\s+Employee"
        r"|Employee[\s'\'s]{0,5}(?:NPS|contribution)[^\n]{0,30}80CCD"
        r"|Amount\s+deductible\s+under\s+section\s+80CCD\s*\(?1B\)?"
        r")",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 10(f): employer NPS contribution u/s 80CCD(2)
    "employer_nps_80ccd2": re.compile(
        r"(?:"
        r"80\s*CCD\s*[\(\[]?\s*2\s*[\)\]]?"
        r"|contribution\s+by\s+Employer\s+to\s+pension"
        r"|Employer[\s'\'s]{0,5}contribution[^\n]{0,40}pension"
        r"|NPS\s+Employer"
        r"|Employer[\s'\'s]{0,5}NPS"
        r")",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 7(a): "Income (or admissible loss) from house property"
    # Also: "Interest on Housing Loan", "Section 24(b)", "Loss from House Property"
    # Value may be negative (loss shown in brackets). Strip sign; caller takes abs().
    "home_loan_interest": re.compile(
        r"(?:"
        r"Income[^\n]{0,30}from\s+house\s+property"
        r"|Loss[^\n]{0,30}house\s+property"
        r"|Interest\s+on\s+(?:Housing|Home)\s+Loan"
        r"|Section\s+24\s*\(?b\)?"
        r"|24\s*\(?b\)?"
        r"|Home\s+Loan\s+Interest"
        r")",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 10(l): section 80TTA / 80TTB — savings account interest
    "savings_interest_80tta": re.compile(
        r"(?:"
        r"80TT[AB]\b"
        r"|interest\s+on\s+deposits\s+in\s+savings"
        r"|Savings\s+(?:Account\s+)?[Ii]nterest"
        r"|Deduction[^\n]{0,30}80TT"
        r")",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------ #
    # Reference only: Form 16 totals for display and cross-checks         #
    # (not mapped to profile fields)                                       #
    # ------------------------------------------------------------------ #

    # Form 16 Part B line 1(d): combined gross salary = basic + HRA + LTA + special allowance.
    # Matches "Salary as per provisions contained in section 17(1)" row total,
    # OR the "Total" label on the same line as the 17(1) amount.
    "gross_salary_17_1": re.compile(
        r"(?:Salary\s+as\s+per\s+provisions\s+contained\s+in\s+section\s+17\s*\(1\)|"
        r"17\s*\(1\))",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 2(e): employer-declared HRA exemption under 10(13A).
    # This is the exempt portion, not the HRA received. It is checked against
    # our Rule 2A figure once the user fills in basic, rent and city.
    "hra_exempt_10_13a": re.compile(
        r"(?:House\s+rent\s+allowance\s+under\s+section\s+10\s*\(13A\)|"
        r"10\s*\(13A\))",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 2(a): employer-declared LTA exemption under 10(5).
    # This is the exempt portion, not the LTA received.
    "lta_exempt_10_5": re.compile(
        r"(?:Travel\s+concession\s+or\s+assistance\s+under\s+section\s+10\s*\(5\)|"
        r"10\s*\(5\))",
        re.IGNORECASE,
    ),
    # Form 16 Part B line 9: "Gross total income (6+8)"
    "gross_total_income": re.compile(
        r"Gross\s+[Tt]otal\s+[Ii]ncome",
        re.IGNORECASE,
    ),
    # Form 16 Part A total TDS column
    "tds_deducted": re.compile(
        r"(?:Total\s+.*?Tax\s+[Dd]educted|TDS\s+[Dd]educted|"
        r"Net\s+tax\s+payable)",
        re.IGNORECASE,
    ),

    # ------------------------------------------------------------------ #
    # Internal — not in PROFILE_FIELDS or REFERENCE_FIELDS                #
    # ------------------------------------------------------------------ #

    # Assessment year — used only by _check_ay_warning(), prefixed with _
    "_assessment_year": re.compile(
        r"(?:Assessment\s+Year|AY)\s*[:\-]?\s*(\d{4}-\d{2,4})",
        re.IGNORECASE,
    ),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

# A money amount: "NIL", grouped digits ("1,50,000", "1,500,000.00") or 3+ plain
# digits, but not section/row references such as "17(1)", "80CCD", "(6+8)",
# "192(2B)", "10(13A)" or receipt numbers glued to letters ("QR12345678").
_AMOUNT_RE = re.compile(
    r"(?<![\w.(+/])"
    r"(NIL|-?\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?|-?\d{3,}(?:\.\d{1,2})?|0(?:\.0{1,2})?)"
    r"(?![\w(+/]|\.\d)",
    re.IGNORECASE,
)
_ROW_START_RE = re.compile(r"^\s*(?:\(\s*[a-z]{1,2}\d?\s*\)|\d{1,2}\s*\.)", re.IGNORECASE)


def _amount_for_row(text: str, start: int, last: bool) -> Optional[str]:
    """
    Return the amount printed on the Form 16 row whose label starts at `start`.

    Looks at the rest of the label's line; if the amount was wrapped onto the
    following line (common with pdfplumber), also looks at that line unless it
    begins a new row ("(b) ...", "7. ..."). Two-column Chapter VI-A rows
    (Gross | Deductible) use the LAST amount; other rows use the first.
    "NIL" is returned as "0".
    """
    line_end = text.find("\n", start)
    line_end = len(text) if line_end == -1 else line_end
    window = text[start:line_end]
    amounts = _AMOUNT_RE.findall(window)
    if not amounts and line_end < len(text):
        nxt_end = text.find("\n", line_end + 1)
        nxt = text[line_end + 1: len(text) if nxt_end == -1 else nxt_end]
        if not _ROW_START_RE.match(nxt):
            amounts = _AMOUNT_RE.findall(nxt)
    if not amounts:
        return None
    raw = amounts[-1] if last else amounts[0]
    return "0" if raw.upper() == "NIL" else raw


def _parse_inr_amount(raw: str) -> float:
    """Parse '1,20,000', '1,200,000' or '120000' to a float by dropping commas."""
    return float(raw.replace(",", "").strip())


def _extract_after_part_b(text: str) -> str:
    """
    Return the text from the Part B header onwards, so Part A's quarterly TDS
    figures aren't mistaken for salary values. Some formats have no Part B
    header; then the whole text is returned.
    """
    pattern = re.compile(
        r"(?:Part\s*[-\u2013]?\s*B|Salary\s+Statement|Schedule\s+1)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        return text[match.start():]
    # No Part B marker — process full text (best-effort)
    logger.debug(
        "Part B marker not found in OCR text — processing full document (best-effort)"
    )
    return text


def _build_confidence(raw_value: Optional[str]) -> str:
    """
    'green' if a value was matched, 'red' if not.

    On a printed Form 16 the uncertainty is mostly whether the label matched,
    not character errors, so a match/no-match rule is simpler and more
    predictable than per-word Tesseract confidence. Scanned values are
    downgraded to yellow separately in extract_form16().
    """
    if raw_value is None:
        return "red"
    return "green"


def _check_ay_warning(text: str) -> list[dict]:
    """
    Extract and validate the assessment year from OCR text.

    Returns a list with one WRONG_AY warning dict if the AY does not match
    AY 2026-27, or an empty list if the AY is correct or not found.

    Handles multiple formats:
    - 'AY 2026-27' / '2026-27' / '2026-2027' → AY2026-27 → OK
    - 'FY 2025-26' → fiscal year → AY2026-27 → OK
    - '2025-26' (no FY marker) → AY2025-26 → WRONG_AY warning
    - 'FY 2024-25' → fiscal year → AY2025-26 → WRONG_AY warning

    Args:
        text: OCR text (full or Part B section)

    Returns:
        List of warning dicts (empty if correct AY or AY not found)
    """
    warnings: list[dict] = []
    match = FIELD_PATTERNS["_assessment_year"].search(text)
    if not match:
        return warnings

    raw_ay = match.group(1).strip()  # e.g. '2025-26' or '2024-25'

    # Parse start year and end year
    parts = raw_ay.split("-")
    start_year = int(parts[0])
    end_part = parts[1]
    # Handle '26' → 2026 and '2026' → 2026
    if len(end_part) == 4:
        end_year = int(end_part)
    else:
        # 2-digit suffix: prefix with century from start_year
        century = (start_year // 100) * 100
        end_year = century + int(end_part)

    # Detect FY vs AY from context (30 chars before the match)
    context_start = max(0, match.start() - 30)
    context_text = text[context_start:match.start()].upper()
    is_fiscal_year = ("F.Y" in context_text or "FY" in context_text) and "AY" not in context_text

    if is_fiscal_year:
        # FY 2025-26 → AY 2026-27
        ay_start = start_year + 1
        ay_end = end_year + 1
    else:
        ay_start = start_year
        ay_end = end_year

    # Valid AY is 2026-27 only (FY 2025-26)
    if not (ay_start == 2026 and ay_end == 2027):
        display = f"AY{ay_start}-{str(ay_end)[-2:]}"
        warnings.append({
            "code": "WRONG_AY",
            "message": (
                f"Form 16 appears to be for {display}. "
                "Please verify you have uploaded the correct year's Form 16."
            ),
        })

    return warnings


def _extract_all_fields(
    text: str,
) -> tuple[dict, dict, dict, list[str], list[dict]]:
    """
    Run every pattern over the Part B text.

    Returns (extracted_fields, profile_fields, reference_fields,
    non_extractable, ay_warnings); see OCRResult for what each holds.
    """
    extracted_fields_raw: dict = {}
    profile_fields_raw: dict = {}
    reference_fields_raw: dict = {}

    for field_name, pattern in FIELD_PATTERNS.items():
        if field_name == "_assessment_year":
            continue  # handled separately via _check_ay_warning

        # Try every label occurrence and take the first that has an amount on
        # its row (e.g. the "1. Gross Salary" heading has no amount; the
        # "(a) Salary as per ... 17(1)" row below it does).
        raw = None
        match = None
        for m in pattern.finditer(text):
            raw = _amount_for_row(text, m.start(), last=field_name in _TAIL_NUMBER_FIELDS)
            match = m
            if raw is not None:
                break
        if match:
            if raw is None:
                value = None
                confidence_str = "red"
            else:
                try:
                    value: Optional[float] = _parse_inr_amount(raw)
                except (ValueError, AttributeError):
                    # malformed number: treat as not found
                    value = None
                    confidence_str = "red"
                else:
                    # Form 16 line 7(a) shows home loan interest as a loss
                    # (negative); the profile field is non-negative.
                    if field_name == "home_loan_interest" and value is not None:
                        value = abs(value)
                    confidence_str = _build_confidence(raw)
        else:
            value = None
            confidence_str = "red"

        field_result = {"value": value, "confidence": confidence_str}

        if field_name in PROFILE_FIELDS:
            extracted_fields_raw[field_name] = field_result
            if value is not None:
                profile_fields_raw[field_name] = value
        elif field_name in REFERENCE_FIELDS:
            # reference fields keep just the value, outside extracted_fields
            reference_fields_raw[field_name] = value

    # basic_salary and gross_salary_17_1 both come from Part B line 1(a)/17(1).
    # Payroll exports often shorten the label ("Salary u/s 17(1)"), which only the
    # 17(1) pattern catches — reuse it, flagged yellow so the user double-checks.
    gross_17_1 = reference_fields_raw.get("gross_salary_17_1")
    if extracted_fields_raw.get("basic_salary", {}).get("value") is None and gross_17_1:
        extracted_fields_raw["basic_salary"] = {"value": gross_17_1, "confidence": "yellow"}
        profile_fields_raw["basic_salary"] = gross_17_1

    ay_warnings = _check_ay_warning(text)
    return (
        extracted_fields_raw,
        profile_fields_raw,
        reference_fields_raw,
        NON_EXTRACTABLE_FIELDS,   # constant list — same for every Form 16
        ay_warnings,
    )


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

_PDFPLUMBER_MIN_CHARS = 200  # Below this threshold → treat as scanned → use Tesseract


def _extract_text_pdfplumber(file_path: str) -> str:
    """
    Read embedded text from the first 4 pages of a PDF. Most payroll-generated
    Form 16s have selectable text. Returns "" on any error.
    """
    import pdfplumber

    try:
        full_text_parts: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:4]:  # Part B is always within first 4 pages
                text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if text:
                    full_text_parts.append(text)
        combined = "\n".join(full_text_parts)
        logger.debug(
            "_extract_text_pdfplumber: extracted %d chars from %s",
            len(combined),
            file_path,
        )
        return combined
    except Exception as exc:
        logger.warning(
            "_extract_text_pdfplumber failed for %s: %s", file_path, exc
        )
        return ""


def _extract_text_tesseract(file_path: str) -> str:
    """
    OCR a scanned PDF or an image with Tesseract (PDF pages are rendered with
    pdf2image first). Slow: a few seconds per page at 300 DPI.
    """
    from pathlib import Path

    import pytesseract
    from pdf2image import convert_from_path
    from PIL import Image

    from backend.config import settings

    # Optional explicit binary paths (Windows dev); Docker/Linux uses PATH.
    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    path = Path(file_path)

    if path.suffix.lower() == ".pdf":
        try:
            images = convert_from_path(
                file_path,
                poppler_path=settings.poppler_path or None,
                dpi=300,          # Tesseract recommended minimum for high accuracy
                first_page=1,
                last_page=4,
            )
        except Exception as exc:
            logger.error("pdf2image failed for %s: %s", file_path, exc)
            return ""
    else:
        # JPEG or PNG — single image file
        images = [Image.open(file_path)]

    full_text = "\n".join(
        pytesseract.image_to_string(img, config=OCR_CONFIG)
        for img in images
    )
    logger.debug(
        "_extract_text_tesseract: extracted %d chars from %s",
        len(full_text),
        file_path,
    )
    return full_text


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_form16(file_path: str) -> "OCRResult":
    """
    Extract Form 16 Part B fields from a .pdf, .jpg or .png that the caller
    has already validated.

    Embedded PDF text is used when there is enough of it; otherwise the file
    is OCR'd with Tesseract. This is CPU-bound, so async callers should run it
    in a worker thread.
    """
    from backend.agents.input_agent.schemas import (
        FieldResult,
        OCRResult,
        OCRSummary,
        OCRWarning,
    )
    from pathlib import Path

    path = Path(file_path)
    extraction_method = "pdfplumber"

    if path.suffix.lower() == ".pdf":
        full_text = _extract_text_pdfplumber(file_path)
    else:
        full_text = ""  # Images go straight to Tesseract below

    # Too little embedded text means a scan; fall back to Tesseract.
    if len(full_text.strip()) < _PDFPLUMBER_MIN_CHARS:
        logger.info(
            "pdfplumber yielded only %d chars — falling back to Tesseract OCR",
            len(full_text.strip()),
        )
        full_text = _extract_text_tesseract(file_path)
        extraction_method = "tesseract"

    logger.info(
        "extract_form16: method=%s total_chars=%d file=%s",
        extraction_method,
        len(full_text),
        path.name,
    )

    part_b_text = _extract_after_part_b(full_text)

    extracted_raw, profile_raw, reference_raw, missing_fields, ay_warnings = (
        _extract_all_fields(part_b_text)
    )

    # Character recognition on scans can drop decimal points or commas (e.g.
    # "29,98,000.00" read as 29,98,00,000), so nothing from Tesseract is "green":
    # every scanned value is shown as needs-review.
    if extraction_method == "tesseract":
        for fr in extracted_raw.values():
            if fr["confidence"] == "green":
                fr["confidence"] = "yellow"

    extracted_fields: dict[str, FieldResult] = {
        k: FieldResult(value=v["value"], confidence=v["confidence"])
        for k, v in extracted_raw.items()
    }

    green_count  = sum(1 for v in extracted_fields.values() if v.confidence == "green")
    yellow_count = sum(1 for v in extracted_fields.values() if v.confidence == "yellow")
    red_count    = sum(1 for v in extracted_fields.values() if v.confidence == "red")

    summary = OCRSummary(
        field_count=len(extracted_fields),
        green_count=green_count,
        yellow_count=yellow_count,
        red_count=red_count,
    )

    warnings = [OCRWarning(**w) for w in ay_warnings]

    logger.info(
        "extract_form16 complete file=%s method=%s green=%d yellow=%d red=%d "
        "missing_fields=%d warnings=%d",
        path.name,
        extraction_method,
        green_count,
        yellow_count,
        red_count,
        len(missing_fields),
        len(warnings),
    )

    return OCRResult(
        extracted_fields=extracted_fields,
        profile_fields=profile_raw,
        reference_fields=reference_raw,
        missing_profile_fields=missing_fields,
        summary=summary,
        warnings=warnings,
    )

