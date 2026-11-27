# TaxMantri

TaxMantri helps salaried people in India decide between the **Old** and **New** income-tax regimes. Upload your Form 16 or type in your salary. It calculates your exact tax under both regimes for **FY 2025-26 (AY 2026-27)**, shows deductions you haven't used, and maps every figure to the ITR-1 return form. A built-in assistant answers tax questions and runs "what if" scenarios on your own numbers.

> Educational tool — not a substitute for a chartered accountant.

---

## Project layout

```
taxmantri-app/
├── backend/                     Python API (FastAPI)
│   ├── main.py                  App start-up, error handling, routes
│   ├── config.py                Settings read from environment variables
│   ├── llm.py                   Gemini client used by every AI feature
│   ├── ratelimit.py             Per-visitor and daily request limits
│   ├── privacy.py               "Delete my data" endpoint and 24-hour clean-up
│   ├── store.py, database.py    Reading and writing to PostgreSQL
│   ├── agents/
│   │   ├── input_agent/         Form 16 reading (OCR), validation, profile endpoints
│   │   ├── evaluator_agent/     Tax engine, deduction tips, ITR-1 mapping, PDF report
│   │   ├── matcher_agent/       Knowledge-base search (embeddings + keyword search)
│   │   └── assistant/           Tool-using chat assistant
│   ├── models/, alembic/        Database tables and migrations
│   └── tests/                   Unit and end-to-end tests
├── frontend/                    Website (React + Vite + Tailwind)
│   └── src/pages, src/components
├── knowledge_base/
│   ├── raw/                     Plain-English summaries of the Income Tax Act sections used
│   └── indexes/                 Pre-built search index shipped with the app
├── eval/                        Accuracy tests: retrieval, OCR, assistant, smoke test
└── docker-compose.yml           Local PostgreSQL + Redis (+ the API in a container)
```

---

## What it does

- **Reads your Form 16.** Upload a PDF or a photo. Salary, exemptions and deductions are extracted and shown for you to check and correct.
- **Compares both regimes exactly.** Covers slab rates, the ₹12 lakh zero-tax rebate (Section 87A) with marginal relief, HRA, 80C, 80D, NPS, home-loan interest, senior-citizen limits and cess.
- **Finds missed savings.** For example: "Invest ₹38,000 more under 80C to save ₹11,400 in the Old regime."
- **Maps figures to ITR-1.** Shows which line of the return each number belongs on, and gives you a downloadable PDF summary.
- **Answers questions.** Ask "What if I put ₹50,000 into NPS?" and the assistant re-runs your numbers and replies in a few sentences, citing the relevant section.
- **Respects privacy.** No account is needed and your name and PAN are never stored. Your data is deleted automatically after 24 hours, or immediately with *Delete my data*.

**Try it without your own data:** click **See a sample result** on the home page.

---

## How it works

```
Form 16 / form ──► OCR + validation ──► your profile
                                            │
                                            ▼
                         Tax engine (plain Python rules, no AI)
                                            │
                 ┌──────────────────────────┴──────────────────────────┐
                 ▼                                                     ▼
     Results: both regimes, tips,                 Assistant (Gemini) decides which tool to use:
     ITR-1 mapping, PDF, a short                   • search the tax-law knowledge base
     explanation citing the law                    • calculate tax  • run a "what if"
```

Three design choices make the results trustworthy:

1. **The numbers never come from AI.** A rule-based tax engine produces every rupee figure. Tests check it against cases worked out by hand. AI is used only to explain results and to hold a conversation.
2. **Hybrid search.** The assistant finds the right section of the law by combining meaning-based search (Gemini embeddings + FAISS) with keyword search (BM25).
3. **An assistant that uses tools.** The model chooses between searching the law, calculating tax and running a scenario, up to four steps per question. If an answer contains a ₹ amount that no tool produced, it is sent back to be rewritten. Answers are kept to about 80–100 words.

---

## Tech stack

| Area | Tools |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy (async), Alembic |
| Data | PostgreSQL, Redis |
| AI and search | Google Gemini (chat + embeddings), FAISS, BM25 |
| Documents | pdfplumber, Tesseract OCR, ReportLab (PDF reports) |
| Frontend | React 18, Vite, Tailwind CSS |
| Quality | pytest, custom evaluation scripts, Docker |

---

## Results

Measured with the scripts in [`eval/`](eval). Each run is saved in [`eval/results/`](eval/results).

| What was tested | Result |
|---|---|
| Finding the right law section, 50 questions | The right section is in the top 5 results **100%** of the time with hybrid search (keyword search alone: 92%) |
| Reading Form 16 text PDFs (30 generated samples, 13 fields each) | 100% of fields correct; 92% on a layout the reader had never seen before a fix |
| Reading scanned Form 16s through OCR | 99.2% of fields correct |
| Assistant answering real questions | Figures match the tax engine in every case; answers are about 80 words |
| End-to-end check of every feature | 17/17 checks pass while using about 150 MB of memory |
| Unit and integration tests | 37 passing |

The Form 16 samples are generated rather than real employer documents, so accuracy on real files may be lower.

---

## Run it locally

You need Python 3.12, Node.js 20+, Docker, and a free Gemini API key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey).

```bash
cp .env.example .env                 # then add your GEMINI_API_KEY
docker compose up -d                 # starts PostgreSQL and Redis

python -m venv .venv
.venv/Scripts/activate               # macOS/Linux: source .venv/bin/activate
pip install -r backend/requirements-dev.txt
uvicorn backend.main:app --reload --port 8000

cd frontend && npm ci && npm run dev # open http://localhost:5173
```

Run the tests and checks:

```bash
pytest                               # unit + integration tests
python -m eval.run_retrieval         # search accuracy
python -m eval.form16_gen && python -m eval.run_ocr   # Form 16 reading accuracy
python -m eval.run_assistant         # assistant answers vs. the tax engine
python -m eval.smoke                 # end-to-end check against a running API
```

To rebuild the search index after editing `knowledge_base/raw/`, run `python -m backend.agents.matcher_agent.build_index`.

---

## API

Interactive docs are served at `/api/docs` when the backend is running.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/profile` | Save salary and deduction details |
| POST | `/api/upload` | Read a Form 16 (PDF/JPG/PNG, max 5 MB) |
| PUT | `/api/profile/confirm` | Confirm the values read from Form 16 |
| POST | `/api/calculate` | Old vs New comparison with explanation |
| GET | `/api/itr1-mapping/{id}` | ITR-1 field mapping |
| GET | `/api/export/{id}` | PDF report |
| POST | `/api/assistant` | Chat assistant (add `?stream=true` for live updates) |
| DELETE | `/api/my-data` | Delete stored data |
| GET | `/api/health` | Health check |

---

## Team

| Name | Role |
|---|---|
| **AMK** | Co-Founder & Developer |
| **Chiru** | Co-Founder & Developer |
| **Srikanth** | Co-Founder & Developer |
| **Rishi** | Co-Founder & Developer |
