# Agent Workflow Evaluation

- Cases: 120 synthetic, template-derived scenarios
- Dataset SHA-256: ce92b8174f806c9fd824ce71f6c920712c0bb2ff6405958a5fe014f771891d30
- Repeats per case: 50
- External detector and single-turn LLM baselines: not run (offline fixture evaluation).
- Latency covers local extraction/routing/draft fixture only; it is not end-to-end performance.

| Split | Cases | Field P | Field R | Field F1 | Route accuracy | Schema validity | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 120 | 0.9975 | 0.9951 | 0.9963 | 0.9917 | 1.0000 | 0.0072 | 0.0091 |
| dev | 96 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0073 | 0.0087 |
| holdout | 24 | 0.9867 | 0.9737 | 0.9801 | 0.9583 | 1.0000 | 0.0068 | 0.0101 |

## Category breakdown

| Category | Cases | Field F1 | Route accuracy |
|---|---:|---:|---:|
| complete_context | 76 | 0.9984 | 0.9868 |
| missing_context | 20 | 1.0000 | 1.0000 |
| negated_claims | 12 | 0.9583 | 1.0000 |
| prompt_injection | 12 | 1.0000 | 1.0000 |

Results are a reproducible local workflow check, not evidence of real-world fraud accuracy.
