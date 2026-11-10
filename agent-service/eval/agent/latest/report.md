# Agent Workflow Evaluation

- Cases: 120 synthetic, template-derived scenarios
- Dataset SHA-256: 4e550e7914a32724508b777c63a86aba02a4c08b7ac6b786df0a5922d79e8ac5
- Repeats per case: 50
- External detector and single-turn LLM baselines: not run (offline fixture evaluation).
- Latency covers local extraction/routing/draft fixture only; it is not end-to-end performance.

| Split | Cases | Field P | Field R | Field F1 | Route accuracy | Schema validity | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 120 | 0.9951 | 1.0000 | 0.9975 | 0.9917 | 1.0000 | 0.0073 | 0.0087 |
| dev | 96 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0074 | 0.0087 |
| holdout | 24 | 0.9747 | 1.0000 | 0.9872 | 0.9583 | 1.0000 | 0.0068 | 0.0091 |

## Category breakdown

| Category | Cases | Field F1 | Route accuracy |
|---|---:|---:|---:|
| complete_context | 76 | 1.0000 | 1.0000 |
| missing_context | 20 | 1.0000 | 1.0000 |
| negated_claims | 12 | 0.9600 | 0.9167 |
| prompt_injection | 12 | 1.0000 | 1.0000 |

Results are a reproducible local workflow check, not evidence of real-world fraud accuracy.
