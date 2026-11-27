# Retrieval eval — 2026-11-27

- Commit `8f04fb6`, embedder `gemini:gemini-embedding-001`, 51 chunks (350 words, overlap 40), 50 questions, RRF k=60

## All questions

| Mode | hit@1 | hit@3 | hit@5 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|---|
| BM25 only | 0.86 | 0.94 | 0.96 | 0.92 | 0.97 | 0.903 |
| FAISS only | 0.96 | 1.00 | 1.00 | 0.98 | 1.00 | 0.980 |
| Hybrid (RRF) | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 | 0.947 |

## Lay questions

| Mode | hit@1 | hit@3 | hit@5 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|---|
| BM25 only | 0.88 | 0.95 | 0.95 | 0.90 | 0.96 | 0.910 |
| FAISS only | 0.95 | 1.00 | 1.00 | 0.98 | 1.00 | 0.975 |
| Hybrid (RRF) | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 | 0.946 |

## Statute questions

| Mode | hit@1 | hit@3 | hit@5 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|---|
| BM25 only | 0.80 | 0.90 | 1.00 | 1.00 | 1.00 | 0.875 |
| FAISS only | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.000 |
| Hybrid (RRF) | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 | 0.950 |
