# usage-service

Usage ledger, budgets (soft/hard), showback summary, anomaly flags
(LLD §2.12 / §4.8 / §5.6). Port **8110**.

## Responsibility

| Type | Role |
|---|---|
| `UsageIngestor` | Idempotent ledger append + budget apply |
| `BudgetService` | Ensure / reserve / commit / upsert |
| `AnomalyDetector` | Per-tenant spike detection |
| `UsageSummaryService` | Showback aggregates |

## API (prefix `/v1`)

- `POST /usage/events` — ingest (201) / idempotent replay (200)
- `GET /usage/summary` — period aggregates (LLD §5.6)
- `GET /usage/budgets` — current budgets
- `PUT /usage/budgets` — upsert limits
- `POST /usage/budgets/reserve|commit`

Headers: `X-Subject-Id`, `X-Tenant-Id`.

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/usage-service[dev]
usage-service
```

## Docker

```bash
cd services/usage-service
docker compose up --build
```

Postgres for the `usage` DB is on host port **5439**.
