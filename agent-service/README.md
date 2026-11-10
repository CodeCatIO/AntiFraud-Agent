# Anti-Fraud Agent Service

The Agent service orchestrates the existing text detector and a read-only, versioned anti-fraud reference index. It produces a review draft with traceable source-card citations; it does not make enforcement decisions or contact external parties.

## Local setup

Run commands from this directory with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m scripts.build_knowledge_index
.\.venv\Scripts\python.exe -m scripts.create_retrieval_dataset
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -m scripts.evaluate_retrieval --repeats 3
```

The MCP endpoint is mounted privately at `/mcp/` and requires `X-Agent-Service-Token`. The only tools are `detect_text` and `search_knowledge`; neither can change a case or execute an external action.

## Workflow durability and data retention

- `CHECKPOINT_DB_PATH` selects the SQLite checkpoint file. Compose sets it to `/data/agent-checkpoints.sqlite` and mounts the named `agent-checkpoint-data` volume.
- `LANGGRAPH_STRICT_MSGPACK=true` enables strict checkpoint serialization. The SQLite saver is intended for one Agent instance and light thesis/demo traffic; do not scale this service to multiple replicas or treat it as a production-grade concurrent database.
- Paused checkpoints contain the submitted and supplemented text. They remain available while awaiting a human action so the workflow can resume after a process restart. After the final event is acknowledged by Spring, the Agent deletes the workflow checkpoint; MySQL remains the business/audit record.
- There is no automatic expiry for runs left waiting for information or review. Restrict access to the volume and backups, and define a retention policy before using non-synthetic personal data. Losing the volume makes unfinished workflows non-resumable.
- The Agent and MCP service ports are not published to the host. Browser clients must call Spring APIs only.

## Knowledge index

- `data/knowledge_sources.jsonl` contains curated source cards with publisher, URL, date, locator, version, retrieval keywords, and an explicit license-review status.
- Each source card becomes a deterministic chunk with a content-derived `chunkId`. Card content is a paraphrase, not a verbatim quotation; API citations identify it as `excerptType: paraphrase`.
- `scripts.build_knowledge_index` validates required metadata and HTTPS URLs, writes an immutable hash-versioned snapshot, then atomically updates `current.json` and `previous.json` pointers.
- Search strategies are `bm25`, sparse lexical `tfidf`, and reciprocal-rank-fusion `hybrid`. TF-IDF is not a neural embedding model. CJK retrieval uses character 2- and 3-grams; immutable snapshots and tokenized terms are cached in-process.
- Roll back the current pointer to the previous index with `.\.venv\Scripts\python.exe -m scripts.build_knowledge_index --rollback`.
- `KNOWLEDGE_SOURCE_PATH` and `KNOWLEDGE_INDEX_DIR` can override the default source and index directories.
- A missing index returns `not_configured`; an empty match returns no citations. The system never fabricates a fallback source.

The current cards include law-article paraphrases, public anti-fraud guidance, and category-level summaries. Some linked 2025/2026 release pages are summaries rather than the full handbook. The content must not be expanded into tactics or facts those pages do not substantiate. `license_status: not_independently_verified` is intentionally not an assertion of reuse permission; verify terms before external publication.

## Retrieval evaluation

`data/retrieval_eval.jsonl` is a deterministic 100-query dataset generated from source-card keywords and titles (80 development, 20 holdout). It is **not human-reviewed**, and its gold labels are source-card IDs rather than expert judgments of semantic relevance. The run writes:

- `eval/results/latest/results.jsonl`: per-query ranks for all strategies;
- `eval/results/latest/summary.json`: Recall@1/3/5, MRR, P50/P95 latency, overall and by split;
- `eval/results/latest/manifest.json`: dataset checksum, index version, environment and limitations;
- `eval/results/latest/report.md`: readable report.

These measurements compare retrieval behavior on a synthetic benchmark only. They do not measure fraud-classification accuracy, citation support judged by humans, production throughput, or real-model quality. Keep the holdout split untouched when tuning and replace or supplement the generated cases with manually reviewed examples before drawing thesis conclusions.

## Agent workflow evaluation

Current benchmark version: v4. Run the commands below to regenerate `data/agent_eval_v4.jsonl` and write the report under `eval/agent/v4/`. The v4 holdout is synthetic and script-validated only; it needs independent human label review. The paragraph below records the historical v3 evaluation and its inspected errors; do not tune against either reported holdout.

Run the deterministic workflow benchmark from this directory:

```powershell
.\.venv\Scripts\python.exe -m scripts.create_agent_eval_dataset
.\.venv\Scripts\python.exe -m scripts.evaluate_agent --repeats 50
```

The v3 dataset contains 120 synthetic cases (96 development, 24 holdout) across complete, incomplete, negated, and prompt-injection contexts. The evaluator reports required-field precision/recall/F1, information-request routing accuracy, draft-schema validity, and local rule/draft latency. It uses fixed detector output and does not call Flask, MCP over the network, or an external LLM. The v3 holdout was authored separately after inspecting earlier holdout errors; use it once for final measurement and do not tune on it. Its labels and templates still require independent student/advisor review before thesis claims. `eval/agent/v3/` stores per-case JSONL, summary, manifest, and Markdown report. The Flask detector has an optional LLM layer, but no live detector or single-turn LLM baseline is represented by this offline score.
