# task-service

Task CRUD, state projection, approvals, event streams, and Temporal start/signal
adapter (LLD §2.5 / §4.5 / §5.4). Port **8103**.

## Responsibility

| Concern | Implementation |
|---|---|
| Create | Policy + budget gate → persist → start workflow → `queued→planning` |
| Lifecycle | cancel / pause / resume with Temporal signals |
| Approvals | request gate → human decide → signal workflow |
| Events | ordered projection + SSE stream |
| State machine | authoritative transitions from LLD §2.5 |

## API (prefix `/v1`)

- `POST /tasks` — create (201)
- `GET /tasks`, `GET /tasks/{id}`
- `POST /tasks/{id}/cancel|pause|resume`
- `GET /tasks/{id}/events`, `GET /tasks/{id}/events/stream` (SSE)
- `GET /tasks/{id}/approvals`
- `POST /approvals/{id}/decide`

Headers: `X-Subject-Id`, `X-Tenant-Id` (gateway-forwarded).

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/task-service[dev]
task-service
```

## Docker

```bash
cd services/task-service
docker compose up --build
```

Postgres for the `task` DB is on host port **5435**.

## Notes

- `TaskWorkflowPort` is an in-memory Temporal stand-in; agent-worker will own real workflows.
- `PolicyPort` currently allows all creates and returns `policy.v1` until policy-service is wired.
- Pause keeps the LLD state enum and sets `paused=true` (pause is a signal, not a distinct state).
