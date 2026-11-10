# Retrieval Evaluation

- Dataset cases: 100 (synthetic templates; not human-reviewed)
- Dataset SHA-256: 825c8d6db55a76aec024564f79ee188cc727fc76659269cf29e9eb1a9c6704cd
- Index version: 1cae7be40108f26f
- Repeats per query: 3
- TF-IDF is a sparse lexical vector baseline; no neural embeddings are used.

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 0.7800 | 0.9600 | 1.0000 | 0.8673 | 2.339 | 2.662 |
| tfidf | 0.8100 | 0.9800 | 1.0000 | 0.8895 | 2.332 | 2.718 |
| hybrid | 0.8300 | 0.9700 | 1.0000 | 0.8953 | 2.331 | 2.735 |

## dev (80 cases)

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 0.9125 | 0.9875 | 1.0000 | 0.9463 | 2.311 | 2.597 |
| tfidf | 0.8875 | 1.0000 | 1.0000 | 0.9417 | 2.290 | 2.621 |
| hybrid | 0.9125 | 0.9875 | 1.0000 | 0.9490 | 2.301 | 2.596 |

## holdout (20 cases)

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 0.2500 | 0.8500 | 1.0000 | 0.5517 | 2.440 | 2.774 |
| tfidf | 0.5000 | 0.9000 | 1.0000 | 0.6808 | 2.505 | 2.813 |
| hybrid | 0.5000 | 0.9000 | 1.0000 | 0.6808 | 2.500 | 2.854 |

Results are offline retrieval measurements, not claims about real-world fraud accuracy.
