# policy-service

Versioned policy bundles and allow / deny / approval-required evaluation
(LLD §2.6 / §4.8 / §5.6). Port **8104**.

## Responsibility

| Concern | Implementation |
|---|---|
| Bundles | Versioned `PolicyBundle` with checksum + object-store ref |
| Engine | `CedarStylePolicyEngine` (OPA/Cedar-class wrapper) |
| Evaluate | Active (or explicit) version → `PolicyDecision` |
| Activate | Retire previous active; one active per tenant |
| Defaults | Seeds `policy.v1` covering tools, models, repos, budgets, data class |

## API (prefix `/v1`)

- `POST /policy/evaluate` — evaluate / dry-run
- `GET /policy/bundles` — list versions
- `POST /policy/bundles` — upsert draft bundle
- `POST /policy/bundles/{version}/activate` — activate version

Headers: `X-Subject-Id`, `X-Tenant-Id` (gateway-forwarded).

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/policy-service[dev]
policy-service
```

## Docker

```bash
cd services/policy-service
docker compose up --build
```

Postgres for the `policy` DB is on host port **5436**.

## Notes

- Default store is in-memory for local/tests; Alembic migration targets Postgres.
- Production plugs a real OPA/Cedar runtime behind `PolicyEngine`; the local engine is deterministic and rule-compatible.
- Callers (task-service / tool-gateway) still use stubs until they wire this client's evaluate API.
