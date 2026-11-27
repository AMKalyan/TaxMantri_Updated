"""
Synthetic Form 16 generator for the OCR evaluation.

Produces N salary profiles (seeded, reproducible) and renders each as a two-page
Form 16 PDF — Part A (TDS summary) and Part B (Annexure, salary statement) — using
the wording of the notified Form No. 16 (Rule 31(1)(a)). Layout and number
formatting vary across samples (Rs./₹ prefixes, NIL for zero, two-column Chapter
VI-A table) so the extractor is not tested against a single template.

Ground truth for every sample is written to <out>/truth.json.

Variants per sample:
  text   — native text PDF (exercises the pdfplumber path)
  scan   — rasterised at 150 DPI with blur, noise and slight rotation, saved as an
           image-only PDF and PNG (exercises the Tesseract path). Needs Poppler, so
           it runs in the Docker image:  python -m eval.form16_gen --scans

Usage:  python -m eval.form16_gen [--n 30] [--seed 2026] [--scans]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "eval" / "data" / "form16" / "generated"

FIRST = ["Arjun", "Priya", "Rahul", "Sneha", "Vikram", "Ananya", "Karthik", "Meera", "Rohan", "Divya"]
LAST = ["Sharma", "Reddy", "Iyer", "Nair", "Gupta", "Patel", "Rao", "Menon", "Das", "Kulkarni"]
EMPLOYERS = ["TechVista Solutions Pvt Ltd", "Northwind Analytics LLP", "Sahyadri Software Ltd", "Coastal Fintech Pvt Ltd"]


def inr(n: float) -> str:
    """Indian digit grouping: 1234567 -> 12,34,567"""
    n = int(round(n))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    return ("-" if n < 0 else "") + s


def make_profile(rng: random.Random, i: int) -> dict:
    gross = rng.randrange(450_000, 4_200_000, 5_000)
    regime_old = rng.random() < 0.5
    hra_exempt = rng.choice([0, 0, rng.randrange(40_000, 300_000, 1_000)]) if regime_old else 0
    lta_exempt = rng.choice([0, 0, 0, rng.randrange(10_000, 60_000, 1_000)]) if regime_old else 0
    pt = rng.choice([0, 2_400, 2_500])
    p = {
        "id": f"F16_{i:03d}",
        "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "employer": rng.choice(EMPLOYERS),
        "regime": "old" if regime_old else "new",
        "gross_salary_17_1": gross,
        "hra_exempt_10_13a": hra_exempt,
        "lta_exempt_10_5": lta_exempt,
        "professional_tax": pt if regime_old else 0,
        "investments_80c": rng.choice([0, rng.randrange(20_000, 150_001, 500), 150_000]) if regime_old else 0,
        "employee_nps_80ccd1b": rng.choice([0, 0, 50_000, rng.randrange(10_000, 50_001, 1_000)]) if regime_old else 0,
        "employer_nps_80ccd2": rng.choice([0, 0, int(gross * 0.4 * rng.choice([0.05, 0.1]))]),
        "health_insurance_self": rng.choice([0, rng.randrange(8_000, 25_001, 500)]) if regime_old else 0,
        "home_loan_interest": rng.choice([0, 0, rng.randrange(50_000, 200_001, 1_000)]) if regime_old else 0,
        "savings_interest_80tta": rng.choice([0, rng.randrange(1_000, 10_001, 100)]) if regime_old else 0,
    }
    std = 50_000 if regime_old else 75_000
    salary_income = gross - hra_exempt - lta_exempt - std - p["professional_tax"]
    p["gross_total_income"] = salary_income - p["home_loan_interest"]
    via = (p["investments_80c"] + p["employee_nps_80ccd1b"] + p["employer_nps_80ccd2"]
           + p["health_insurance_self"] + p["savings_interest_80tta"])
    p["total_taxable_income"] = max(0, p["gross_total_income"] - via)
    p["tds_deducted"] = int(max(0, (p["total_taxable_income"] - 700_000) * 0.12)) // 10 * 10
    p["basic_salary"] = gross   # extractor maps 17(1) gross salary to basic_salary
    return p


def render(p: dict, path: Path, rng: random.Random) -> None:
    style = rng.choice(["rs", "rupee", "plain"])
    nil_word = rng.random() < 0.5

    def amt(v: float) -> str:
        if v == 0 and nil_word:
            return "NIL"
        prefix = {"rs": "Rs. ", "rupee": "", "plain": ""}[style]
        dec = ".00" if style != "plain" else ""
        return f"{prefix}{inr(v)}{dec}"

    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y = h - 50

    def line(text: str, value: str | None = None, value2: str | None = None, bold=False, size=8.5):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(40, y, text)
        if value2 is not None:
            c.drawRightString(470, y, value or "")
            c.drawRightString(560, y, value2)
        elif value is not None:
            c.drawRightString(560, y, value)
        y -= 14

    # ---------------- Part A ----------------
    line("FORM NO. 16", bold=True, size=12)
    line("[See rule 31(1)(a)]")
    line("Certificate under section 203 of the Income-tax Act, 1961 for tax deducted at source on salary")
    line("PART A", bold=True)
    line(f"Name and address of the Employer: {p['employer']}")
    line(f"Name and address of the Employee: {p['name']}")
    line("PAN of the Deductor: AABCT1234C        TAN of the Deductor: HYDB12345E")
    line("Assessment Year: 2026-27        Period with the Employer: 01-04-2025 to 31-03-2026")
    line("Summary of amount paid/credited and tax deducted at source thereon in respect of the employee")
    q = p["tds_deducted"] // 4
    for i, qt in enumerate(("Q1", "Q2", "Q3", "Q4")):
        line(f"{qt}   Receipt No. QR{rng.randrange(10**7, 10**8)}", amt(p["gross_salary_17_1"] / 4), amt(q if i < 3 else p["tds_deducted"] - 3 * q))
    line("Total (Rs.)", amt(p["gross_salary_17_1"]), amt(p["tds_deducted"]), bold=True)
    c.showPage()
    y = h - 50

    # ---------------- Part B ----------------
    line("PART B (Annexure)", bold=True, size=11)
    line("Details of Salary Paid and any other income and tax deducted")
    line("Whether opting out of taxation u/s 115BAC?   " + ("Yes" if p["regime"] == "old" else "No"))
    line("1. Gross Salary", bold=True)
    line("(a) Salary as per provisions contained in section 17(1)", amt(p["gross_salary_17_1"]))
    line("(b) Value of perquisites under section 17(2)", amt(0))
    line("(c) Profits in lieu of salary under section 17(3)", amt(0))
    line("(d) Total", amt(p["gross_salary_17_1"]), bold=True)
    line("2. Less: Allowances to the extent exempt under section 10", bold=True)
    line("(a) Travel concession or assistance under section 10(5)", amt(p["lta_exempt_10_5"]))
    line("(b) Death-cum-retirement gratuity under section 10(10)", amt(0))
    line("(e) House rent allowance under section 10(13A)", amt(p["hra_exempt_10_13a"]))
    line("(h) Total amount of exemption claimed under section 10", amt(p["hra_exempt_10_13a"] + p["lta_exempt_10_5"]))
    line("3. Total amount of salary received from current employer [1(d)-2(h)]",
         amt(p["gross_salary_17_1"] - p["hra_exempt_10_13a"] - p["lta_exempt_10_5"]))
    line("4. Less: Deductions under section 16", bold=True)
    line("(a) Standard deduction under section 16(ia)", amt(50_000 if p["regime"] == "old" else 75_000))
    line("(b) Entertainment allowance under section 16(ii)", amt(0))
    line("(c) Tax on employment under section 16(iii)", amt(p["professional_tax"]))
    line("5. Total amount of deductions under section 16 [4(a)+4(b)+4(c)]",
         amt((50_000 if p["regime"] == "old" else 75_000) + p["professional_tax"]))
    line('6. Income chargeable under the head "Salaries" [(3+1(e)-5]',
         amt(p["gross_total_income"] + p["home_loan_interest"]))
    line("7. Add: Any other income reported by the employee under as per section 192(2B)", bold=True)
    hp = -p["home_loan_interest"]
    line("(a) Income (or admissible loss) from house property reported by employee offered for TDS", amt(hp) if hp else amt(0))
    line("(b) Income under the head Other Sources offered for TDS", amt(0))
    line("9. Gross total income (6+8)", amt(p["gross_total_income"]), bold=True)
    line("10. Deductions under Chapter VI-A", "Gross Amount", "Deductible Amount", bold=True)
    line("(a) Deduction in respect of life insurance premia, contributions to provident fund etc. under section 80C",
         amt(p["investments_80c"]), amt(p["investments_80c"]))
    line("(b) Deduction in respect of contribution to certain pension funds under section 80CCC", amt(0), amt(0))
    line("(c) Deduction in respect of contribution by taxpayer to pension scheme under section 80CCD(1)", amt(0), amt(0))
    line("(d) Total deduction under section 80C, 80CCC and 80CCD(1)", amt(p["investments_80c"]), amt(p["investments_80c"]))
    line("(e) Deductions in respect of amount paid/deposited to notified pension scheme under section 80CCD(1B)",
         amt(p["employee_nps_80ccd1b"]), amt(p["employee_nps_80ccd1b"]))
    line("(f) Deduction in respect of contribution by Employer to pension scheme under section 80CCD(2)",
         amt(p["employer_nps_80ccd2"]), amt(p["employer_nps_80ccd2"]))
    line("(g) Deduction in respect of health insurance premia under section 80D",
         amt(p["health_insurance_self"]), amt(p["health_insurance_self"]))
    line("(h) Deduction in respect of interest on loan taken for higher education under section 80E", amt(0), amt(0))
    line("(k) Deduction in respect of interest on deposits in savings account under section 80TTA",
         amt(p["savings_interest_80tta"]), amt(p["savings_interest_80tta"]))
    via = p["gross_total_income"] - p["total_taxable_income"]
    line("11. Aggregate of deductible amount under Chapter VI-A", amt(via), bold=True)
    line("12. Total taxable income (9-11)", amt(p["total_taxable_income"]), bold=True)
    line("19. Net tax payable (17-18)", amt(p["tds_deducted"]), bold=True)
    c.showPage()
    c.save()


def render_compact(p: dict, path: Path, rng: random.Random) -> None:
    """
    HOLD-OUT layout (never used while tuning the extractor): HR-software style
    abbreviated labels, the rupee sign, and amounts wrapped onto the line BELOW
    the label, as payroll exports often render.
    """
    def amt(v: float) -> str:
        return "₹ 0.00" if v == 0 else f"₹ {inr(v)}.00"

    c = canvas.Canvas(str(path), pagesize=A4)
    w, h = A4
    y = h - 50

    def put(text: str, size=9, bold=False, x=40):
        nonlocal y
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(x, y, text)
        y -= 13

    def row(label: str, *values: float):
        put(label)
        put("    ".join(amt(v) for v in values), x=300)

    put("Form 16 - TDS Certificate on Salary", 12, True)
    put(f"Employer: {p['employer']}   Employee: {p['name']}")
    put("AY: 2026-27   FY: 2025-26")
    put(f"Total TDS for the year: {amt(p['tds_deducted'])}")
    c.showPage(); y = h - 50
    put("Part B - Salary Computation", 11, True)
    row("Salary u/s 17(1) (Basic + Allowances)", p["gross_salary_17_1"])
    row("Perquisites u/s 17(2)", 0)
    row("Less: LTA exemption u/s 10(5)", p["lta_exempt_10_5"])
    row("Less: Exempt HRA u/s 10(13A)", p["hra_exempt_10_13a"])
    row("Standard Deduction u/s 16(ia)", 50_000 if p["regime"] == "old" else 75_000)
    row("Professional Tax u/s 16(iii)", p["professional_tax"])
    row("Loss from House Property (interest on housing loan)", -p["home_loan_interest"] if p["home_loan_interest"] else 0)
    row("Gross Total Income", p["gross_total_income"])
    put("Chapter VI-A Deductions (Gross / Deductible)", bold=True)
    row("Section 80C - PF, LIC, ELSS (Total)", p["investments_80c"], p["investments_80c"])
    row("80CCD(1B) - NPS (Employee)", p["employee_nps_80ccd1b"], p["employee_nps_80ccd1b"])
    row("80CCD(2) - NPS (Employer contribution)", p["employer_nps_80ccd2"], p["employer_nps_80ccd2"])
    row("80D - Medical Insurance Premium", p["health_insurance_self"], p["health_insurance_self"])
    row("80TTA - Savings Account Interest", p["savings_interest_80tta"], p["savings_interest_80tta"])
    row("Total Taxable Income", p["total_taxable_income"])
    row("Net Tax Payable", p["tds_deducted"])
    c.showPage()
    c.save()


def make_scan(pdf: Path, rng: random.Random) -> list[Path]:
    from pdf2image import convert_from_path
    from PIL import ImageFilter
    import numpy as np
    from PIL import Image

    pages = convert_from_path(str(pdf), dpi=150)
    out_pages = []
    for img in pages:
        img = img.convert("L").rotate(rng.uniform(-1.2, 1.2), expand=True, fillcolor=255)
        img = img.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.3, 0.8)))
        arr = np.asarray(img, dtype=np.int16)
        arr = np.clip(arr + np.random.default_rng(rng.randrange(1 << 30)).normal(0, 12, arr.shape), 0, 255)
        out_pages.append(Image.fromarray(arr.astype("uint8")))
    scan_pdf = pdf.with_name(pdf.stem + "_scan.pdf")
    out_pages[0].save(scan_pdf, save_all=True, append_images=out_pages[1:], resolution=150)
    png = pdf.with_name(pdf.stem + "_partB.png")
    out_pages[-1].save(png)
    return [scan_pdf, png]


def main(n: int, seed: int, scans: bool, layout: str = "official") -> None:
    rng = random.Random(seed)
    out = OUT if layout == "official" else OUT.parent / f"generated_{layout}"
    out.mkdir(parents=True, exist_ok=True)
    truth = []
    for i in range(1, n + 1):
        p = make_profile(rng, i)
        pdf = out / f"{p['id']}.pdf"
        (render if layout == "official" else render_compact)(p, pdf, rng)
        variants = {"text": pdf.name}
        if scans:
            scan_pdf, png = make_scan(pdf, rng)
            variants.update({"scan_pdf": scan_pdf.name, "scan_png": png.name})
        p["files"] = variants
        truth.append(p)
    (out / "truth.json").write_text(json.dumps({"seed": seed, "layout": layout, "samples": truth}, indent=1), encoding="utf-8")
    print(f"Generated {n} Form 16 samples ({layout}) in {out} (scans={'yes' if scans else 'no'})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--scans", action="store_true")
    ap.add_argument("--layout", default="official", choices=["official", "compact"])
    a = ap.parse_args()
    main(a.n, a.seed, a.scans, a.layout)
