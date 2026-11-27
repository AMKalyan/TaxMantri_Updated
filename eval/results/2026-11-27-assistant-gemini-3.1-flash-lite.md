# Assistant eval — 2026-11-27

- Commit `12b8849`, Gemini `gemini-3.1-flash-lite` — **6/7 passed**

| Case | Result | Tools | Time | Missing / forbidden |
|---|---|---|---|---|
| whatif_nps | pass | get_my_profile, what_if | 61.1s | — |
| my_current_tax | pass | get_my_profile, what_if | 34.7s | — |
| hypothetical_14L | pass | calculate_tax | 50.5s | — |
| zero_tax_1275 | pass | calculate_tax | 48.1s | — |
| itr1_two_houses | pass | search_tax_law | 8.1s | — |
| 80c_limit | FAIL | — | 73.5s | 1,50,000 |
| marginal_relief | pass | search_tax_law | 24.8s | — |
