# indexing-worker

Queue consumer that turns repository snapshots into searchable index generations
(LLD §2.14 / §7 / §4.7).

## Responsibility

`Snapshot → classify → parse → enrich → chunk → embed → publish`

| Component | Role |
|---|---|
| `IndexingPipeline` | Stage orchestrator |
| `RepoClassifier` | Languages, binaries, secrets, skip |
| `TreeSitterFacade` | AST/symbols (Python in first slice) |
| `SemanticChunker` | Symbol / section / line-window chunks |
| `EmbeddingBatcher` | Deduped batch embed via Model Gateway port |
| `IndexPublisher` | Two-phase publish + activate |
| `IncrementalDiffEngine` | Manifest path+hash diff |

## First vertical slice

- **Single language:** Python (stdlib AST behind `TreeSitterFacade`)
- Unsupported languages: line-window chunking + lexical path; coverage metric flagged
- Embeddings: `DeterministicEmbedder` locally; production swaps to Model Gateway
- Default store: in-memory (tests/local); Postgres `index_meta` via Alembic for deploy

## Run locally

```bash
pip install -e packages/py-alama-common
pip install -e workers/indexing-worker[dev]
indexing-worker
```

## Docker

```bash
cd workers/indexing-worker
docker compose up --build
```

Postgres for `index_meta` is exposed on host port **5434**.

## Migrations

```bash
alembic upgrade head
```

## Consume a job (programmatic)

Enqueue `IndexJob` on the worker queue (from repository-service outbox
`com.alama.repository.snapshot.requested.v1` in production). Tests seed the
in-memory queue and call `process_one`.

## OpenAPI

Not applicable — this deployable is a queue consumer, not an HTTP API.
Retrieval remains in `retrieval-service` (next module).
