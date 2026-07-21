# Alama eval golden suites

Versioned fixtures consumed by `evaluator-worker` (LLD §15 / monorepo layout).

| Suite | Path | Metrics |
|---|---|---|
| Retrieval | `retrieval/` | recall@k, MRR |
| Agent | `agent/` | success_rate |
| Safety | `safety/` | fail_rate |
| Cost | `cost/` | tokens, usd_micros |

Suites are versioned (`v1`, …). Worker loads by `suite_version` on each job.
