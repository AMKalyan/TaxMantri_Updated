"""
OCR extraction evaluation against synthetic Form 16 ground truth.

Each extracted field is scored as an exact match after normalisation (amounts are
compared as integers). Outcomes per field:
  correct  — extracted value equals truth
  wrong    — a value was extracted but differs
  missing  — no value extracted (truth may be 0; a zero truth with no extraction
             counts as correct because the extractor treats NIL/absent as empty)

Usage (repository root):
  python -m eval.form16_gen            # text PDFs
  python -m eval.run_ocr               # score text PDFs
  python -m eval.run_ocr --variant scan_pdf   # needs Tesseract + Poppler (Docker)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "eval" / "data" / "form16" / "generated"
RESULTS = ROOT / "eval" / "results"

PROFILE_FIELDS = [
    "basic_salary", "professional_tax", "investments_80c", "health_insurance_self",
    "employee_nps_80ccd1b", "employer_nps_80ccd2", "home_loan_interest", "savings_interest_80tta",
]
REFERENCE_FIELDS = ["gross_salary_17_1", "hra_exempt_10_13a", "lta_exempt_10_5", "gross_total_income", "tds_deducted"]


def norm(v) -> int | None:
    if v is None:
        return None
    try:
        return int(round(abs(float(v))))
    except (TypeError, ValueError):
        return None


def main(variant: str, tag: str, layout: str = "official") -> None:
    from backend.agents.input_agent.ocr_service import extract_form16

    gen = GEN if layout == "official" else GEN.parent / f"generated_{layout}"
    truth = json.loads((gen / "truth.json").read_text(encoding="utf-8"))["samples"]
    fields = PROFILE_FIELDS + REFERENCE_FIELDS
    stats = {f: {"correct": 0, "wrong": 0, "missing": 0} for f in fields}
    failures = []
    perfect_docs = 0

    for s in truth:
        fname = s["files"].get(variant)
        if not fname:
            raise SystemExit(f"Variant '{variant}' not generated — run python -m eval.form16_gen --scans")
        r = extract_form16(str(gen / fname))
        got = {k: v.value for k, v in r.extracted_fields.items()}
        got.update(r.reference_fields or {})
        doc_ok = True
        for f in fields:
            exp, val = norm(s[f]), norm(got.get(f))
            if val is None:
                outcome = "correct" if exp == 0 else "missing"
            elif val == exp:
                outcome = "correct"
            else:
                outcome = "wrong"
            stats[f][outcome] += 1
            if outcome != "correct":
                doc_ok = False
                failures.append({"sample": s["id"], "field": f, "expected": exp, "got": val, "outcome": outcome})
        perfect_docs += doc_ok

    n = len(truth)
    total = {k: sum(v[k] for v in stats.values()) for k in ("correct", "wrong", "missing")}
    cells = n * len(fields)
    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit = "unknown"
    report = {
        "layout": layout,
        "date": dt.date.today().isoformat(), "commit": commit, "variant": variant, "samples": n,
        "field_accuracy": round(total["correct"] / cells, 4),
        "wrong_rate": round(total["wrong"] / cells, 4), "missing_rate": round(total["missing"] / cells, 4),
        "documents_fully_correct": perfect_docs, "per_field": stats, "failures": failures,
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    stem = f"{report['date']}-ocr-{layout}-{variant}" + (f"-{tag}" if tag else "")
    (RESULTS / f"{stem}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        f"# OCR eval — {report['date']} (layout={layout}, variant={variant})", "",
        f"- Commit `{commit}`, {n} synthetic Form 16s, {len(fields)} fields each",
        f"- Field accuracy **{report['field_accuracy']:.1%}** · wrong {report['wrong_rate']:.1%} · "
        f"missing {report['missing_rate']:.1%} · documents fully correct {perfect_docs}/{n}", "",
        "| Field | Correct | Wrong | Missing | Accuracy |", "|---|---|---|---|---|",
    ]
    for f in fields:
        st = stats[f]
        lines.append(f"| {f} | {st['correct']} | {st['wrong']} | {st['missing']} | {st['correct'] / n:.0%} |")
    (RESULTS / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if failures:
        print(f"\nFirst failures: {failures[:8]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="text", choices=["text", "scan_pdf", "scan_png"])
    ap.add_argument("--tag", default="")
    ap.add_argument("--layout", default="official", choices=["official", "compact"])
    a = ap.parse_args()
    main(a.variant, a.tag, a.layout)
