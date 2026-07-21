# retrieval-service

Synchronous, commit-consistent hybrid retrieval on port **8105** (LLD §2.7 / §9).

Pipeline: query formulation → pre-authorized lexical/vector/symbol search → weighted
RRF → one-hop graph expansion → Model Gateway rerank → post-filter → token-budgeted
evidence and citations.

## API

`POST /v1/retrieve` requires `X-Tenant-Id`. The request identifies repository,
commit, query, ACL labels and token budget. Ancestor fallback is disabled by default;
when explicitly allowed, the response is marked `stale=true`.

Repository content is untrusted evidence. Consumers must not execute instructions
from retrieval results.

## Local verification

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/retrieval-service[dev]
pytest
mypy src
ruff check src tests
```

The in-memory adapters model index metadata, lexical search, vector search and graph
adjacency for deterministic tests. Production adapters read `index_meta`, managed
vectors and OpenSearch through the same narrow ports.
