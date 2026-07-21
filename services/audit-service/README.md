# audit-service

Append-only audit events with integrity hash chain, query, export, and legal hold
(LLD §2.11 / §4.8 / §5.6 / §13.5). Port **8109**.

## Responsibility

| Type | Role |
|---|---|
| `AuditIngestor` | Validate → object store → append → outbox |
| `IntegrityHasher` | SHA-256 hash chain per tenant |
| `AuditQueryService` | Tenant-scoped cursor search + chain verify |
| `AuditExporter` | Region-aware export package |
| `LegalHoldService` | Freeze / release + audited |

## API (prefix `/v1`)

- `POST /audit/events` — ingest (201)
- `GET /audit/events` — list with filters (LLD §5.6)
- `GET /audit/integrity` — verify hash chain
- `POST /audit/exports` — export package
- `POST/DELETE /audit/legal-hold`

Headers: `X-Subject-Id`, `X-Tenant-Id`.

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/audit-service[dev]
audit-service
```

## Docker

```bash
cd services/audit-service
docker compose up --build
```

Postgres for the `audit` DB is on host port **5438**.
