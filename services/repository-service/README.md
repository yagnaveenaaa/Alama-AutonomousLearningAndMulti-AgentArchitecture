# repository-service

Repository Ops bounded context (LLD §2.4).

## Purpose

Owns **SCM installations**, **repository connections**, **webhook intake**, and **snapshot intents**. Clone credentials are referenced only via `SecretRef` (secret manager path) — never stored as raw secrets.

## Key types

| Type | Role |
|---|---|
| `Installation` | SCM app installation |
| `RepositoryConnection` | Connected repo under an installation |
| `WebhookDelivery` | Deduplicated inbound webhook |
| `RepoSnapshot` | Commit-addressed indexing unit |
| `ScmProvider` | Provider port (`GithubScmAdapter`, `GitlabScmAdapter`, `BitbucketScmAdapter`) |
| `WebhookIngestor` | Verify → dedupe → outbox |
| `SnapshotRequestService` | Enqueue reindex snapshot |
| `PermissionRefreshService` | Refresh SCM ACL projection |

## API (port 8102)

| Method | Path |
|---|---|
| GET | `/health` |
| POST | `/v1/installations` |
| GET | `/v1/repositories` |
| GET | `/v1/repositories/{id}` |
| POST | `/v1/repositories/connect` |
| DELETE | `/v1/repositories/{id}` |
| POST | `/v1/repositories/{id}/reindex` → 202 |
| GET | `/v1/repositories/{id}/snapshots` |
| GET | `/v1/repositories/{id}/index/status` |
| POST | `/webhooks/{provider}` → 202 |

Gateway headers: `X-Subject-Id`, `X-Tenant-Id`.

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/repository-service[dev]
cd services/repository-service
pytest
uvicorn repository_service.main:app --port 8102
```

## Docker

```bash
cd services/repository-service
docker compose up --build
```

## Ownership

- **Team:** Repository Ops
- **Schema:** `repository` (LLD §4.4)
