# Retrieval eval — 2026-11-27

- Commit `c69a1d2`, embedder `none`, 51 chunks (None words, overlap None), 50 questions, RRF k=60

## All questions

| Mode | hit@1 | hit@3 | hit@5 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|---|
| BM25 only | 0.86 | 0.94 | 0.96 | 0.92 | 0.97 | 0.903 |

## Lay questions

| Mode | hit@1 | hit@3 | hit@5 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|---|
| BM25 only | 0.88 | 0.95 | 0.95 | 0.90 | 0.96 | 0.910 |

## Statute questions

| Mode | hit@1 | hit@3 | hit@5 | recall@5 | recall@10 | MRR |
|---|---|---|---|---|---|---|
| BM25 only | 0.80 | 0.90 | 1.00 | 1.00 | 1.00 | 0.875 |
