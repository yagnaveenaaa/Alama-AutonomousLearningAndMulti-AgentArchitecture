# identity-service

Identity & Access bounded context (LLD §2.3).

## Purpose

Owns **tenants**, **subjects**, **memberships**, **role bindings**, and **API keys** (hashed). External IdP remains the authentication source of truth; this service stores projections and authorization metadata.

## Responsibilities

| Component | Role |
|---|---|
| `Tenant` | Aggregate root — org, home cell/region, isolation tier |
| `Subject` | User projection keyed by `external_idp_sub` |
| `MembershipService` | Enforces active-tenant membership rules |
| `CreateTenantHandler` | Provisions tenant + owner subject + `owner` role |
| `ApiKeyService` | Issues Argon2-hashed keys; plaintext returned once |
| `ScimSyncHandler` | Upserts subjects from SCIM/OIDC admin hooks |

## API (port 8101)

| Method | Path | Auth |
|---|---|---|
| GET | `/health` | none |
| POST | `/v1/tenants` | none (bootstrap) |
| GET | `/v1/tenants/me` | `X-Subject-Id`, `X-Tenant-Id` |
| GET | `/v1/subjects/me` | gateway headers |
| GET | `/v1/tenants/{tid}/subjects` | gateway headers |
| POST | `/v1/tenants/{tid}/api-keys` | gateway headers |
| DELETE | `/v1/tenants/{tid}/api-keys/{id}` | gateway headers |

Interactive docs: `http://localhost:8101/docs`  
OpenAPI: `openapi.yaml` and `/openapi.json`

## Local run

```bash
# From monorepo root
pip install -e packages/py-alama-common[fastapi]
pip install -e services/identity-service[dev]

cd services/identity-service
pytest
uvicorn identity_service.main:app --host 0.0.0.0 --port 8101
```

Default store is **in-memory** (`IDENTITY_USE_IN_MEMORY_STORE=true`) for local/dev without Postgres.

## Database

- Schema: `identity` (LLD §4.3)
- Migrations: Alembic under `migrations/`
- Apply (Postgres): `alembic upgrade head`

## Docker

```bash
# From services/identity-service
docker compose up --build
```

## Ownership

- **Team:** Identity & Access
- **SLO:** Control-plane identity reads contribute to 99.95% API target
