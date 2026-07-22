# bff-web

GraphQL composition BFF for the web UI (LLD §2.2). Port **8081**. No database —
aggregates task / repository / knowledge / usage cell APIs.

## Responsibility

| Module | Role |
|---|---|
| `schema` | GraphQL types: Task, Repo, Memory, Usage, Chat |
| `dataloaders` | Per-request cache to prevent N+1 |
| `auth_context` | Forward `X-Subject-Id` / `X-Tenant-Id` |
| `mappers` | Service DTO → GraphQL types |
| `ServiceClients` | Typed clients (in-memory locally) |

Never exposes vendor IDs or raw model payloads.

## Endpoints

| Path | Purpose |
|---|---|
| `GET /health` | Liveness |
| `POST /graphql` | GraphQL |
| `GET /graphql` | GraphiQL |
| `GET /schema.graphql` | SDL export |

## Example

```graphql
query Dashboard {
  tasks { id title state repositoryName }
  repositories { id fullName indexState }
  usage { tokensUsed tokensBudget }
}
```

Headers: `X-Subject-Id`, `X-Tenant-Id` (from api-gateway / session bridge).

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/bff-web[dev]
bff-web
```

## Docker

```bash
cd services/bff-web
docker compose up --build
```

## Notes

- Default clients are in-memory fixtures aligned to `apps/web` mock shapes.
- **Vertical slice:** set `BFF_ENABLE_VERTICAL_SLICE=true` (and install
  `workers/indexing-worker`, `workers/agent-worker`, `packages/py-alama-slice`).
  `sendChat` then runs import → index → agent → approval against
  `fixtures/auth-bug-repo`. See `compose/run-vertical-slice.ps1`.
- `sendChat` returns messages + `StreamHandshake.streamUrl` for SSE against task events.
- HTTP clients to live cell services plug in behind the same ports when `use_in_memory_clients=false`.
