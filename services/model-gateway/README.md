# model-gateway

Internal-only path to LLM and embedding providers (LLD §2.9). Port **8107**.

## Responsibility

| Module | Role |
|---|---|
| `ModelRouter` | Select model by capability / cost / residency |
| `ProviderAdapter` | Vendor SDK isolation |
| `PromptTemplateRegistry` | Immutable named templates (`planner.v1`, …) |
| `RedactionFilter` | Strip secrets before egress |
| `EgressPolicy` | Training prohibition / deny flags |
| `UsageEmitter` | Token accounting events |
| Quotas | Per-tenant token budget enforcement |

## Internal API

Mirrors LLD §5.7 `ModelGateway.Complete / Embed / Rerank`:

- `POST /v1/complete`
- `POST /v1/embed`
- `POST /v1/rerank`

Header: `X-Tenant-Id` (required). Not a public edge API.

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/model-gateway[dev]
model-gateway
```

## Docker

```bash
cd services/model-gateway
docker compose up --build
```
