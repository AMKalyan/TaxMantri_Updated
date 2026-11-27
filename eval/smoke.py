"""
End-to-end smoke test against a running API (local Docker or the deployed URL).

  python -m eval.smoke                         # http://127.0.0.1:8000
  python -m eval.smoke https://<your>.onrender.com

Exercises: health, manual profile → calculate → ITR-1 mapping → PDF, Form 16 upload →
confirm → calculate, delete-my-data, removed debug endpoints, upload size limit,
and that forged X-Forwarded-For values do not bypass the rate limiter.
Needs eval/data/form16/generated/F16_001.pdf (python -m eval.form16_gen).
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import httpx

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
SAMPLE = Path(__file__).resolve().parent / "data" / "form16" / "generated" / "F16_001.pdf"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=90)

    r = c.get("/api/health")
    check("health", r.status_code == 200, r.text[:80])

    profile = {"input_method": "manual", "basic_salary": 900000, "hra_received": 360000,
               "special_allowance": 300000, "monthly_rent_paid": 25000, "city_type": "metro",
               "age_bracket": "under60", "investments_80c": 150000, "health_insurance_self": 25000}
    r = c.post("/api/profile", json=profile)
    check("create profile", r.status_code == 200, str(r.status_code))
    pid = r.json().get("profile_id") if r.status_code == 200 else None

    if pid:
        r = c.post("/api/calculate", json={"profile_id": pid})
        ok = r.status_code == 200 and "old_regime" in r.json()
        body = r.json() if r.status_code == 200 else {}
        check("calculate", ok, f"old={body.get('old_regime', {}).get('total_tax')} "
                               f"new={body.get('new_regime', {}).get('total_tax')} rec={body.get('recommended_regime')}")
        r = c.get(f"/api/itr1-mapping/{pid}")
        check("itr1 mapping", r.status_code == 200, f"{len(r.json()) if r.status_code == 200 else r.status_code} rows")
        r = c.get(f"/api/export/{pid}")
        check("pdf export", r.status_code == 200 and r.content[:4] == b"%PDF", f"{len(r.content)} bytes")

    if SAMPLE.exists():
        r = c.post("/api/upload", files={"file": ("form16.pdf", SAMPLE.read_bytes(), "application/pdf")})
        check("form16 upload", r.status_code == 200, str(r.json().get("summary") if r.status_code == 200 else r.text[:120]))
        if r.status_code == 200:
            sid = r.json()["session_id"]
            r = c.put("/api/profile/confirm", json={"session_id": sid, "edited_fields": {
                "monthly_rent_paid": 30000, "city_type": "metro", "age_bracket": "under60"}})
            check("confirm OCR profile", r.status_code == 200, r.text[:120])
            if r.status_code == 200:
                opid = r.json()["profile_id"]
                r = c.post("/api/calculate", json={"profile_id": opid})
                check("calculate OCR profile", r.status_code == 200, str(r.status_code))
                r = c.request("DELETE", "/api/my-data", json={"profile_id": opid, "session_id": sid})
                check("delete my data", r.status_code == 200, r.text[:120])
                r = c.get(f"/api/profile/{opid}")
                check("deleted profile is gone", r.status_code == 404, str(r.status_code))
    else:
        check("form16 sample present", False, "run python -m eval.form16_gen first")

    # --- AI layer (uses a few LLM calls) ---
    if pid:
        r = c.post("/api/calculate", json={"profile_id": pid})
        cites = r.json().get("citations", []) if r.status_code == 200 else []
        check("calculate has law citations", len(cites) > 0, f"{len(cites)} citations")
    r = c.post("/api/assistant", json={"question": "What is the maximum deduction under section 80C?",
                                       "session_id": str(uuid.uuid4())})
    ans = r.json().get("answer", "") if r.status_code == 200 else r.text[:120]
    check("assistant answers (JSON)", r.status_code == 200 and "1,50,000" in ans.replace("150,000", "1,50,000"), ans[:90])
    with c.stream("POST", "/api/assistant?stream=true",
                  json={"question": "I earn 14 lakh salary. How much tax in the new regime?",
                        "session_id": str(uuid.uuid4())}) as s:
        events = [line[7:] for line in s.iter_lines() if line.startswith("event: ")]
    check("assistant streams steps then done", "step" in events and events[-1:] == ["done"], f"events={events}")

    r = c.post("/api/upload", files={"file": ("big.pdf", b"%PDF-1.4\n" + b"0" * (6 * 1024 * 1024), "application/pdf")})
    check("oversized upload rejected", r.status_code in (413, 422), str(r.status_code))

    for path in ("/api/ocr-debug?file_path=/etc/passwd", "/api/run"):
        r = c.request("GET" if "debug" in path else "POST", path, json={} if "run" in path else None)
        check(f"removed endpoint {path.split('?')[0]}", r.status_code in (404, 405), str(r.status_code))

    # Forged X-Forwarded-For must not give a fresh rate-limit bucket each time.
    statuses = []
    for i in range(25):
        r = c.post("/api/profile", json=profile, headers={"X-Forwarded-For": f"10.9.{i}.{uuid.uuid4().int % 250}"})
        statuses.append(r.status_code)
    check("rate limit not bypassed by forged XFF", 429 in statuses, f"statuses seen: {sorted(set(statuses))}")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
