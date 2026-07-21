# evaluator-worker

Batch/async eval jobs for retrieval recall, agent success, attribution/safety,
and cost. Writes scorecards and canary gate decisions (LLD §2.16 / §15).

**No HTTP port** — queue consumer only. Never blocks the agent hot path except
via canary promote/block gates consumed by CD.

## Responsibility

| Component | Role |
|---|---|
| `EvalRunner` | Job → grader → scorecard |
| `CanaryGate` | Threshold + regression → promote/block |
| Graders | Deterministic recall@k, success, attribution, safety, cost |
| `GoldenSetStore` | Versioned suite fixtures (`evals/`) |

## Job kinds

- `retrieval_recall` — recall@k / MRR
- `agent_success` — outcome match rate
- `attribution` — unsupported claim rate
- `safety` — injection corpus fail rate
- `cost` — tokens / USD micros

## Local run

```bash
pip install -e packages/py-alama-common
pip install -e workers/evaluator-worker[dev]
evaluator-worker
```

## Docker

```bash
cd workers/evaluator-worker
docker compose up --build
```

Postgres for the `eval` DB is on host port **5441**.

## Programmatic consume

```python
from evaluator_worker.container import build_container
from evaluator_worker.domain.models import EvalJob, EvalKind
from evaluator_worker.main import process_one

container = build_container()
await container.queue.enqueue(EvalJob.create(...))
await process_one(container)
```
