# Alama

Autonomous AI software engineering platform — turn a software objective into a safe, reviewable, tested change across authorized repositories.

This monorepo implements the architecture in:

| Document | Role |
|---|---|
| [`Alama-Production-Architecture-v1.1.md`](./Alama-Production-Architecture-v1.1.md) | High-level / production target architecture |
| [`Alama-Low-Level-Design-v1.0.md`](./Alama-Low-Level-Design-v1.0.md) | Implementation blueprint (contracts, modules, ports) |

Local defaults use **in-memory stores** so you can run without Postgres, Kafka, or Temporal.

---

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.12+ |
| Node.js | 20+ |
| Docker / Docker Compose | Optional (recommended for full stack) |
| Git | Any recent version |

---

## Quick start

### Option A — Docker Compose (recommended)

From the monorepo root:

```bash
# Minimal: identity + API gateway + BFF + web UI
docker compose -f compose/docker-compose.yml --profile core up --build

# AI path: core + task/repo/policy/retrieval/knowledge/model/tool + indexing + agent workers
docker compose -f compose/docker-compose.yml --profile ai up --build

# Everything: ai + audit/usage/notification/evaluator + Redis + MailHog
docker compose -f compose/docker-compose.yml --profile full up --build
```

Stop:

```bash
docker compose -f compose/docker-compose.yml --profile core down
# or --profile ai / --profile full
```

### Option B — Local processes (Windows / no Docker)

```powershell
# from monorepo root
.\compose\run-local-core.ps1
```

Starts identity, API gateway, BFF, and the Next.js app in minimized windows. On some Windows hosts port **8080** is reserved; the script binds the gateway to **18080**.

Stop by closing those windows or ending the `uvicorn` / `node` processes.

---

## Local URLs

| Surface | URL |
|---|---|
| Web UI | http://localhost:3000 |
| API Gateway | http://localhost:8080 (`18080` with `run-local-core.ps1`) |
| BFF GraphQL | http://localhost:8081 |
| Identity (OpenAPI) | http://localhost:8101/docs |
| MailHog UI (`full` profile) | http://localhost:8025 |

Health checks:

```bash
curl http://localhost:8101/health
curl http://localhost:8080/health   # or :18080 locally on Windows
curl http://localhost:8081/health
```

---

## Compose profiles

| Profile | What starts |
|---|---|
| `core` | identity, api-gateway, bff-web, alama-web |
| `ai` | core + repository, task, policy, retrieval, knowledge, model-gateway, tool-gateway, indexing-worker, agent-worker |
| `full` | ai + audit, usage, notification, evaluator-worker, Redis, MailHog |

More detail: [`compose/README.md`](./compose/README.md).

---

## Service ports

| Service | Port |
|---|---|
| api-gateway | 8080 |
| bff-web | 8081 |
| identity-service | 8101 |
| repository-service | 8102 |
| task-service | 8103 |
| policy-service | 8104 |
| retrieval-service | 8105 |
| knowledge-service | 8106 |
| model-gateway | 8107 |
| tool-gateway | 8108 |
| audit-service | 8109 |
| usage-service | 8110 |
| notification-service | 8111 |
| alama-web | 3000 |
| Redis (`full`) | 6379 |

Workers (`indexing-worker`, `agent-worker`, `evaluator-worker`) do not expose HTTP ports.

---

## Run a single service (local Python)

From the monorepo root, install the shared package once, then the service:

```bash
pip install -e "packages/py-alama-common[fastapi]"
pip install -e "services/identity-service[dev]"
identity-service
# or: uvicorn identity_service.main:app --host 127.0.0.1 --port 8101
```

Same pattern for other backends (replace the path / console script):

```bash
pip install -e "services/api-gateway[dev]"
api-gateway

pip install -e "services/task-service[dev]"
task-service

pip install -e "services/bff-web[dev]"
bff-web
```

Each service README under `services/*/README.md` and `workers/*/README.md` documents its own run/Docker notes.

---

## Frontend only

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000 — middleware sends you to `/login` until a local session cookie is set.

```bash
npm run typecheck
npm test
npm run build
npm start
```

Details: [`apps/web/README.md`](./apps/web/README.md).

---

## Shared Python package

```bash
pip install -e "packages/py-alama-common[dev]"
cd packages/py-alama-common
pytest
mypy src
ruff check src tests
```

---

## Tests

```bash
# Shared library
cd packages/py-alama-common && pytest

# Example service tests (from that service directory)
cd services/identity-service && pytest
cd services/api-gateway && pytest
cd services/task-service && pytest

# Frontend
cd apps/web && npm test
```

Eval golden suites used by `evaluator-worker` live under [`evals/`](./evals/README.md).

---

## Repository layout

```
alama/
├─ apps/web/                 Next.js UI
├─ services/                 Domain microservices (FastAPI)
├─ workers/                  Indexing, agent, evaluator workers
├─ packages/py-alama-common/ Shared Python primitives
├─ compose/                  Local Docker Compose + Windows helper script
├─ evals/                    Retrieval / agent / safety / cost fixtures
├─ Alama-Production-Architecture-v1.1.md
└─ Alama-Low-Level-Design-v1.0.md
```

### Backend services

| Path | Role |
|---|---|
| `services/api-gateway` | Edge auth, routing, rate limits, proxy |
| `services/bff-web` | GraphQL BFF for the web app |
| `services/identity-service` | Tenants, subjects, memberships |
| `services/repository-service` | SCM connections, webhooks, sync |
| `services/task-service` | Tasks, approvals, event streams |
| `services/policy-service` | Allow/deny decisions (Cedar/OPA-class) |
| `services/retrieval-service` | Hybrid search / RAG retrieval |
| `services/knowledge-service` | Governed org memory |
| `services/model-gateway` | LLM provider abstraction |
| `services/tool-gateway` | Capability tokens + tool broker |
| `services/audit-service` | Append-only audit evidence |
| `services/usage-service` | Metering and budgets |
| `services/notification-service` | Email / Slack / in-product events |

### Workers

| Path | Role |
|---|---|
| `workers/indexing-worker` | Parse, chunk, embed, publish index generations |
| `workers/agent-worker` | Planner → executor → verifier workflows |
| `workers/evaluator-worker` | Offline / async quality and cost evals |

---

## Architecture (short)

```
Developer (Web / IDE / CLI)
        ↓
API Gateway + BFF
        ↓
Control plane (identity, placement, policy)
        ↓
Regional cell (tasks, repos, retrieval, model/tool gateways)
        ↓
Workers + sandboxed execution
        ↓
Data plane (Postgres, object storage, vector, Redis, Kafka)  — production target
```

Local development skips most of the data plane and uses in-memory adapters.

---

## Dev token (API gateway)

Local gateway can mint a JWT for manual API calls:

```bash
curl -X POST http://localhost:8080/v1/gateway/dev/mint-token
```

Use the returned bearer token on subsequent `/v1/**` requests. See [`services/api-gateway/README.md`](./services/api-gateway/README.md).

---

## Documentation map

| Want to… | Read |
|---|---|
| Understand product vision & ADRs | `Alama-Production-Architecture-v1.1.md` |
| Implement a service / contract | `Alama-Low-Level-Design-v1.0.md` |
| Run local stack | `compose/README.md` (this README’s Quick start) |
| Work on one service | `services/<name>/README.md` |

---

## Status

Reference architecture with a growing vertical-slice implementation. Defaults favor maintainability and production boundaries over demo speed. Not production-ready as a deployed multi-tenant SaaS without the full cell / Temporal / Kafka / sandbox fabric described in the HLD.
