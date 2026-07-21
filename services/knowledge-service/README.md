# knowledge-service

Governed memory items, conversation threads, write gates, and retention
(LLD §2.8 / §4.6 / §5.5 / §8). Port **8106**.

## Responsibility

| Concern | Implementation |
|---|---|
| Memory CRUD | Candidate → active via `MemoryWriteGate` |
| Write gate | PII/secret/dedupe/confidence/policy checks |
| Conversations | Thread + sequenced messages with content refs |
| Retention | Expiry + legal hold (`RetentionJob`) |
| Content | `MemoryContentStore` object refs (in-memory locally) |

## API (prefix `/v1`)

- `GET /memories`, `POST /memories` (201 / 422 gate reject)
- `PATCH /memories/{id}`, `DELETE /memories/{id}` (204)
- `GET /conversations`, `POST /conversations`
- `POST /conversations/{id}/messages` (201, or 202 when `start_task`)

Headers: `X-Subject-Id`, `X-Tenant-Id` (gateway-forwarded).

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/knowledge-service[dev]
knowledge-service
```

## Docker

```bash
cd services/knowledge-service
docker compose up --build
```

Postgres for the `knowledge` DB is on host port **5437**.

## Notes

- Soft delete propagates: PG row → content store delete (vector tombstone hook deferred).
- Optional semantic index adapter is a future port; metadata lives in `memory_items`.
