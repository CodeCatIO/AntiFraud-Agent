# Retrieval Evaluation

- Dataset cases: 100 (synthetic templates; not human-reviewed)
- Dataset SHA-256: 825c8d6db55a76aec024564f79ee188cc727fc76659269cf29e9eb1a9c6704cd
- Index version: 1cae7be40108f26f
- Repeats per query: 3
- TF-IDF is a sparse lexical vector baseline; no neural embeddings are used.

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 0.7800 | 0.9600 | 1.0000 | 0.8673 | 6.565 | 7.759 |
| tfidf | 0.8100 | 0.9800 | 1.0000 | 0.8895 | 6.594 | 7.693 |
| hybrid | 0.8300 | 0.9700 | 1.0000 | 0.8953 | 6.571 | 7.963 |

## dev (80 cases)

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 0.9125 | 0.9875 | 1.0000 | 0.9463 | 6.504 | 7.378 |
| tfidf | 0.8875 | 1.0000 | 1.0000 | 0.9417 | 6.539 | 7.690 |
| hybrid | 0.9125 | 0.9875 | 1.0000 | 0.9490 | 6.535 | 7.957 |

## holdout (20 cases)

| Strategy | Recall@1 | Recall@3 | Recall@5 | MRR | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|
| bm25 | 0.2500 | 0.8500 | 1.0000 | 0.5517 | 6.721 | 8.543 |
| tfidf | 0.5000 | 0.9000 | 1.0000 | 0.6808 | 6.760 | 7.833 |
| hybrid | 0.5000 | 0.9000 | 1.0000 | 0.6808 | 6.808 | 8.047 |

Results are offline retrieval measurements, not claims about real-world fraud accuracy.
