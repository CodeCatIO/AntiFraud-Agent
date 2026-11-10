# Agent Workflow Evaluation

- Cases: 120 synthetic, template-derived scenarios
- Dataset SHA-256: ae8a1100f4df2789aa0d23755e6859fc83bfe36055666ba82d93893886f6218f
- Repeats per case: 50
- External detector and single-turn LLM baselines: not run (offline fixture evaluation).
- Latency covers local extraction/routing/draft fixture only; it is not end-to-end performance.

| Split | Cases | Field P | Field R | Field F1 | Route accuracy | Schema validity | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all | 120 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0071 | 0.0100 |
| dev | 96 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0071 | 0.0099 |
| holdout | 24 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 0.0063 | 0.0104 |

## Category breakdown

| Category | Cases | Field F1 | Route accuracy |
|---|---:|---:|---:|
| complete_context | 76 | 1.0000 | 1.0000 |
| missing_context | 20 | 1.0000 | 1.0000 |
| negated_claims | 12 | 1.0000 | 1.0000 |
| prompt_injection | 12 | 1.0000 | 1.0000 |

Results are a reproducible local workflow check, not evidence of real-world fraud accuracy.
