# Local Compose (LLD §11.2)

Not for production. Boots Alama services with **in-memory** defaults.

## Profiles

| Profile | What starts |
|---|---|
| `core` | identity, api-gateway, bff-web, alama-web |
| `ai` | core + task/repo/policy/retrieval/knowledge/model/tool + indexing + agent workers |
| `full` | ai + audit/usage/notification/evaluator + redis + mailhog |

## Docker

```bash
# from monorepo root
docker compose -f compose/docker-compose.yml --profile core up --build
```

| Surface | URL |
|---|---|
| Web | http://localhost:3000 |
| API Gateway | http://localhost:8080 (local script uses **18080** if 8080 is blocked) |
| BFF GraphQL | http://localhost:8081 |
| Identity | http://localhost:8101/docs |

## Without Docker (Windows / local Python)

```powershell
# from monorepo root
.\compose\run-local-core.ps1
```

Starts the same core processes via uvicorn + `next dev`. On some Windows hosts port **8080** is reserved; the script binds the gateway to **18080**.
