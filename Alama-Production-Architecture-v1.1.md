# Alama — Production Software Architecture
**Version 1.1** · Autonomous AI Software Engineering Platform  
**Status:** Reference architecture (target state)  
**Optimization criterion:** Long-term maintainability and production readiness (not implementation speed)

---

## Table of contents

1. [Vision](#1-vision)
2. [Problem statement](#2-problem-statement)
3. [Architectural principles](#3-architectural-principles)
4. [Functional requirements](#4-functional-requirements)
5. [Non-functional requirements and SLOs](#5-non-functional-requirements-and-slos)
6. [High-level architecture](#6-high-level-architecture)
7. [Detailed component architecture](#7-detailed-component-architecture)
8. [Agent architecture](#8-agent-architecture)
9. [Memory system](#9-memory-system)
10. [RAG pipeline](#10-rag-pipeline)
11. [Repository understanding pipeline](#11-repository-understanding-pipeline)
12. [API Gateway](#12-api-gateway)
13. [Backend services](#13-backend-services)
14. [Frontend architecture](#14-frontend-architecture)
15. [Database design](#15-database-design)
16. [Vector database design](#16-vector-database-design)
17. [Redis cache design](#17-redis-cache-design)
18. [Authentication](#18-authentication)
19. [Security](#19-security)
20. [CI/CD](#20-cicd)
21. [Docker](#21-docker)
22. [Kubernetes](#22-kubernetes)
23. [Monitoring](#23-monitoring)
24. [Logging](#24-logging)
25. [Cost optimization](#25-cost-optimization)
26. [Folder structure](#26-folder-structure)
27. [Coding standards](#27-coding-standards)
28. [Development roadmap](#28-development-roadmap)
29. [Design decision trade-offs](#29-design-decision-trade-offs)
30. [Definition of architectural success](#30-definition-of-architectural-success)

---

## Architecture stance

Alama uses a **global control plane** for identity, placement, policy distribution, and commercial metadata. Repository data and agent execution stay inside a tenant’s assigned **regional cell**. Large enterprises may receive a **dedicated cell**.

Where multiple approaches are reasonable, this document states trade-offs and picks the option that ages best under scale, security review, and multi-team ownership.

### Target SLOs (initial)

| Metric | Target |
|---|---|
| Control-plane availability | 99.95% |
| Concurrent global tasks | 100k+ |
| Incremental index freshness (p95) | < 2 min |
| Agent credential model | Zero trust (short-lived capabilities) |

---

## 1. Vision

- Turn a software objective into a safe, reviewable, tested change across any authorized repository.
- Combine autonomous execution with enterprise governance: every action is scoped, attributable, reproducible, and interruptible.
- Operate as a multi-model engineering system, not a thin chat wrapper: understand repositories, plan work, execute tools, verify results, and learn from outcomes.

---

## 2. Problem statement

- Engineering context is fragmented across source, history, issues, documentation, CI, runtime telemetry, and human conventions.
- General-purpose models lack durable repository understanding and can make plausible but unsafe changes without constrained tools and independent verification.
- Enterprise adoption requires tenant isolation, regional data residency, policy enforcement, audit evidence, predictable spend, and integration with existing developer workflows.
- Repository-scale indexing and agent workloads are bursty, expensive, and heterogeneous; synchronous request-response systems do not scale economically.

---

## 3. Architectural principles

1. **Cell-based multi-tenancy** — bound blast radius and scale by adding regional execution cells.
2. **Async by default** — durable workflows and event streams separate user latency from long-running work.
3. **Zero-trust agents** — agents receive short-lived, least-privilege capabilities, never ambient credentials.
4. **Evidence before action** — retrieval results, policy decisions, tool outputs, and verification artifacts remain traceable.
5. **Model and vendor portability** — route through internal contracts; do not expose provider APIs to product services.
6. **Human authority** — approval gates are policy-driven and mandatory for high-impact operations.

---

## 4. Functional requirements

| Capability | Required behavior | Priority |
|---|---|---|
| Repository lifecycle | Connect GitHub, GitLab, Bitbucket, or enterprise Git; webhook sync; branch/PR operations; monorepo support. | P0 |
| Repository intelligence | Incremental parsing, symbol graph, dependency graph, semantic index, conventions, ownership, build/test discovery. | P0 |
| Autonomous tasks | Clarify, plan, edit, run tools, test, review, recover, checkpoint, pause, resume, cancel. | P0 |
| Collaboration | Chat, task timeline, live logs, diff review, approval gates, comments, notifications, IDE and SCM handoff. | P0 |
| Governance | RBAC/ABAC, policy packs, model/tool allowlists, budgets, retention, legal hold, immutable audit export. | P0 |
| Integrations | Issue trackers, CI, observability, secrets managers, artifact registries, knowledge sources, MCP-compatible tools. | P1 |
| Learning loop | Outcome capture, evaluator scores, accepted/rejected changes, reusable organization knowledge with consent. | P1 |
| Enterprise operations | SSO, SCIM, private networking, customer-managed keys, data residency, dedicated cells, SLA reporting. | P1 |

---

## 5. Non-functional requirements and SLOs

| Quality | Target |
|---|---|
| Availability | 99.95% control-plane API; 99.9% task execution; cell failure must not cross cell boundary. |
| Durability | No acknowledged task or audit event loss; workflow state RPO ≤ 5 min, RTO ≤ 30 min per region. |
| Latency | API p95 < 300 ms excluding streams; first task event < 2 s; indexed retrieval p95 < 500 ms. |
| Scale | Millions of repositories, 100k+ concurrent tasks globally, horizontal ingestion and execution. |
| Isolation | Tenant-scoped authorization on every access; enterprise option for dedicated data plane and encryption keys. |
| Consistency | Strong consistency for identity, policy, billing, and workflow transitions; eventual consistency for search/index freshness. |
| Freshness | Webhook changes searchable in < 2 min p95; full initial index target < 30 min for a 1 GB repository. |
| Observability | End-to-end traceability from API request through model calls, tools, workflow transitions, and spend. |
| Compliance | Architecture supports SOC 2 Type II, ISO 27001, GDPR, SLSA, and configurable regional retention. |

> Targets are initial architecture objectives and must become measured service-level indicators before contractual use.

---

## 6. High-level architecture

```
Developer surfaces (Web, IDE, CLI, SCM app, API)
        ↓
Global edge (CDN, WAF, API gateway, DDoS defense)
        ↓
Control plane (Identity, tenant placement, plans, policy distribution)
        ↓
Regional cell (Tasks, repositories, retrieval, model and tool gateways)
        ↓
Execution fabric (Isolated sandboxes, runners, browser and CI tools)
        ↓
Data plane (PostgreSQL, object storage, vector, cache, event log)
```

Each cell is a complete horizontal slice with independent compute, queues, databases, vector partitions, encryption keys, and operational quotas. A tenant is pinned to one home cell. Cross-cell access is denied by default; global services retain only the minimum routing and commercial metadata needed to locate that tenant.

**Why cells instead of shared-everything or dedicated-everything:** Shared-everything ships faster but fails enterprise isolation and blast-radius requirements. Dedicated-everything isolates well but cannot economically serve millions of repositories. Cells accept platform complexity in exchange for density today and dedicated isolation tomorrow without rewriting product APIs.

### Control plane (global)

- Tenant directory and cell placement
- Federated identity and entitlement catalog
- Policy/model catalog distribution
- Global status, usage rollups, and support tooling

### Execution cell (regional)

- Repository and task services
- Workflow orchestration and agent runtime
- Index, retrieval, memory, model, and tool gateways
- Cell-local observability, metering, and audit pipeline

### Sandbox fabric (isolated)

- MicroVM or hardened pod per execution
- Ephemeral filesystem from immutable snapshot
- Explicit egress allowlist and resource limits
- Short-lived capability token for each tool call

---

## 7. Detailed component architecture

| Component | Responsibility | State / scaling |
|---|---|---|
| API Gateway / BFF | HTTP, GraphQL, WebSocket/SSE edge; auth, quotas, routing, response shaping. | Stateless; regional active-active |
| Identity & Tenant | Organizations, users, groups, roles, entitlements, SSO/SCIM mappings. | Strongly consistent |
| Repository Service | Connections, installations, refs, webhook state, permissions, sync intents. | PostgreSQL + object storage |
| Task Service | Task API, approvals, task metadata, event projection, cancellation. | PostgreSQL + workflow engine |
| Workflow Orchestrator | Durable agent lifecycle, retries, timers, compensation, human waits. | Temporal-class platform |
| Agent Runtime | Planner/executor/verifier loops; context assembly; tool invocation. | Ephemeral isolated workers |
| Tool Gateway | Capability issuance, policy checks, sandbox RPC, output limits, audit. | Stateless + Redis |
| Model Gateway | Provider abstraction, routing, fallback, quotas, prompt policy, token accounting. | Stateless + Kafka ledger |
| Indexing Service | Clone snapshots, parse, chunk, enrich, embed, publish index versions. | Queue-driven workers |
| Retrieval Service | Hybrid search, graph expansion, ACL filtering, reranking, citations. | Vector + lexical + graph views |
| Knowledge Service | Organization memory, decisions, runbooks, feedback, provenance, retention. | PostgreSQL + vector store |
| Policy Service | OPA-style policy decisions for tools, data, models, approvals, egress. | Versioned policy bundles |
| Audit Service | Append-only normalized events, export, legal hold, compliance evidence. | Kafka + immutable object store |
| Usage & Billing | Token, compute, storage, tool and egress metering; budgets and showback. | Event ledger + warehouse |
| Notification Service | Email, Slack/Teams, webhooks, in-product events. | Async delivery |

---

## 8. Agent architecture

The agent is a durable state machine coordinated by the workflow engine. Model responses propose typed intentions; only the Tool Gateway can authorize side effects. Every state transition is checkpointed and replay-safe.

```
Task intake → Context builder → Planner → Executor → Verifier → Outcome
   (goal,       (evidence &      (milestones,  (edits &     (tests,     (PR, evidence,
    repo,        constraints)     risks, gates)  tools)       checks)     memory)
    budget)
```

### Roles and control loop

- **Orchestrator:** deterministic lifecycle, budgets, retries, deadlines, cancellation, and approvals.
- **Planner:** decomposes objectives into a dependency-aware plan with explicit success criteria.
- **Repository specialist:** retrieves symbols, call paths, history, conventions, ownership, and relevant tests.
- **Executor:** applies minimal changes inside the sandbox; it cannot directly access cloud credentials.
- **Verifier:** independently evaluates diff scope, tests, policy, security findings, and objective completion.
- **Reviewer:** uses a separate prompt and preferably separate model family for high-risk tasks.
- **Recovery agent:** classifies failures, rolls back to checkpoint, narrows scope, or escalates to a human.
- **Summarizer:** produces user-facing rationale, citations, artifacts, and memory candidates.

### Safety invariants

- Typed tool schemas, output size limits, timeouts, idempotency keys, and explicit read/write classification.
- Policy evaluated at task admission and again at every sensitive tool call using current context.
- No production deployment, protected-branch write, secret read, destructive migration, or external message without the configured approval.
- Prompt injection is treated as untrusted repository data; retrieved instructions never override system or tenant policy.
- Token, wall-clock, compute, and tool budgets stop runaway loops; repeated failures trigger circuit breakers.
- Checkpoints include plan, workspace snapshot, tool receipts, model metadata, and workflow sequence.

---

## 9. Memory system

Memory is governed knowledge, not an unbounded transcript. Every item has scope, type, provenance, confidence, ACL, retention, and expiry. Raw prompts are not promoted automatically.

| Layer | Examples | Storage | Lifecycle |
|---|---|---|---|
| Working memory | Current plan, observations, active files, tool results | Workflow state + encrypted object blobs | Task lifetime; compacted at checkpoints |
| Episodic memory | What was attempted, failures, accepted outcome | PostgreSQL metadata + object store + vector index | Tenant retention; quality-gated |
| Semantic memory | Architecture decisions, conventions, domain facts, runbooks | Knowledge service + vector index | Versioned; owner review and expiry |
| Procedural memory | Approved workflows, tool recipes, test strategies | Policy-controlled templates | Explicit publication; immutable versions |
| Repository memory | Symbols, dependencies, summaries, ownership, tests | Snapshot index stores | Commit-addressed; replaced incrementally |

### Memory write gate

Candidate extraction → PII/secret scan → deduplication → provenance check → confidence/evaluator score → tenant policy → optional owner approval → publish.

Deletion propagates to object, vector, cache, and derived-index tombstones.

---

## 10. RAG pipeline

1. **Query formulation** — Classify intent and construct multiple bounded queries from task, plan step, repository state, and user identity.
2. **Scope and authorization** — Resolve tenant, repository, commit, path ACL, classification, and residency before retrieval.
3. **Candidate generation** — Run lexical search, dense vector search, symbol lookup, graph traversal, and recent-history retrieval in parallel.
4. **Fusion** — Use reciprocal-rank fusion with source-specific weights; exact symbols and current-commit matches outrank semantic similarity.
5. **Graph expansion** — Add callers, callees, imports, tests, ownership, configuration, and adjacent documentation within a strict budget.
6. **Reranking** — Cross-encoder or strong-model reranker scores task relevance, freshness, authority, and diversity.
7. **Context packing** — Pack by information value per token; preserve source boundaries, line references, commit SHA, and trust labels.
8. **Generation and grounding** — The agent must cite evidence IDs; unsupported claims are flagged by an attribution evaluator.
9. **Feedback** — Record retrieval traces, selected evidence, acceptance, latency, and cost for offline evaluation—never cross tenant boundaries.

Retrieval is commit-consistent. If the requested commit is not indexed, the service searches the nearest ancestor only when policy permits and labels the result stale.

---

## 11. Repository understanding pipeline

1. **Ingest** — Provider webhooks enter a durable event log; deduplicate by delivery ID and reconcile periodically to recover missed events.
2. **Snapshot** — Fetch through a hardened Git service, verify object integrity, resolve submodules/LFS by policy, and write an immutable commit manifest.
3. **Classify** — Detect languages, frameworks, generated/vendor/binary files, secrets, licenses, build systems, and repository size tier.
4. **Parse** — Use tree-sitter/compiler front ends for AST and symbols; extract definitions, references, imports, call edges, tests, APIs, and configuration.
5. **Enrich** — Join CODEOWNERS, blame/history, PRs, issues, CI outcomes, docs, coverage, and optional runtime telemetry with provenance.
6. **Chunk and summarize** — Prefer semantic units—symbol, class, module, document section—using hierarchical summaries; avoid arbitrary fixed windows except fallback.
7. **Embed and publish** — Batch embeddings, create vector and lexical documents, build graph adjacency, then atomically publish a new index version.
8. **Incremental update** — Diff commit manifests; reprocess changed semantic units and reverse dependencies; tombstone removed items; compact asynchronously.

**Very large repositories:** Sparse checkout, path-priority tiers, language-aware worker pools, reusable content-hash artifacts, and hot/warm/cold index classes prevent a monorepo from monopolizing a cell.

**Index quality gates:** Parser coverage, unresolved symbol rate, retrieval recall benchmarks, stale-index age, embedding drift, duplicate ratio, and ACL leakage tests block publication when thresholds fail.

---

## 12. API Gateway

- Global anycast DNS/CDN and WAF terminate at the nearest compliant edge; tenant directory routes to the home cell.
- REST for public resource APIs, GraphQL for web aggregation, WebSocket/SSE for task events; internal services use versioned gRPC.
- OAuth/OIDC validation, tenant resolution, request IDs, schema validation, body limits, idempotency, quotas, and abuse protection.
- Rate limits are hierarchical: IP, subject, tenant, repository, task class, and model budget. Redis enforces local limits; global budgets use the usage ledger.
- No business authorization at the edge alone. Services re-evaluate resource permissions and policy.
- External APIs use date/version headers, compatibility windows, generated contracts, pagination, and signed webhooks.

---

## 13. Backend services

- Domain-aligned services with explicit ownership; avoid one service per table and avoid a distributed monolith.
- Transactional outbox publishes domain events after database commit; consumers are idempotent and maintain inbox/deduplication state.
- Temporal-class durable workflows own long operations; Kafka-class streams carry facts, telemetry, metering, and indexing work.
- Sagas provide compensation across repository, sandbox, and PR operations; no cross-service distributed transactions.
- Backpressure uses per-tenant fair queues, weighted concurrency, admission control, dead-letter queues, and retry budgets.
- All contracts carry `tenant_id`, trace context, schema version, actor, and data-classification metadata.

---

## 14. Frontend architecture

- Next.js/React TypeScript web application behind CDN; server rendering only for public/login shells, client rendering for authenticated workspaces.
- Feature modules by domain: tasks, repositories, review, policies, administration, usage, integrations.
- A BFF composes cell APIs and prevents provider-specific and internal service contracts from leaking to the browser.
- TanStack Query-class server-state cache; local UI state remains separate. Task events update normalized cache through resumable streams.
- Large diffs, logs, and repository trees use virtualization and incremental loading; binary/secret content is never rendered by default.
- WCAG 2.2 AA, keyboard-first workflows, internationalization boundaries, CSP nonces, Trusted Types, and dependency integrity checks.
- Task experience: objective → plan → live timeline → approvals → diff/evidence → PR handoff.
- Event streams are sequence-numbered; reconnect resumes from the last acknowledged event and falls back to projection polling.
- Optimistic updates only for reversible preferences and comments, never approval or policy decisions.
- Frontend telemetry excludes prompts, source, secrets, and diff content by default; tenant admins control optional diagnostics.
- Contract tests validate BFF schemas; component accessibility, visual regression, and critical end-to-end flows gate releases.
- Micro-frontends are deferred. A modular monolith reduces operational and UX inconsistency until independent release cadence is proven necessary.

---

## 15. Database design

PostgreSQL-compatible regional clusters are the system of record. Each cell starts with separate logical databases for control metadata, tasks/workflows, and knowledge/usage, then physically splits only when load or compliance requires it.

| Relation | Key fields | Notes |
|---|---|---|
| tenants | tenant_id, home_region, plan, isolation_tier, status | Tenant root; region and lifecycle boundary |
| users / groups / memberships | subject IDs, tenant_id, role bindings | Identity projection; external IdP remains source |
| repositories | repo_id, tenant_id, provider, external_id, default_ref | Connection metadata; no source blobs |
| repo_snapshots | snapshot_id, repo_id, commit_sha, index_version, state | Immutable indexing unit |
| tasks | task_id, tenant_id, repo_id, state, workflow_id, budget | Authoritative task record |
| task_events | event_id, task_id, sequence, type, payload_ref | Ordered projection; large payloads externalized |
| approvals | task_id, gate, decision, subject_id, policy_version | Non-repudiable human decisions |
| memory_items | memory_id, scope, type, content_ref, provenance, expiry | Durable governed memory metadata |
| policies | policy_id, tenant_id, version, bundle_ref, status | Immutable versions; explicit activation |
| credentials | credential_id, provider_ref, scope metadata | Only secret-manager references, never secret values |
| usage_ledger | usage_id, tenant_id, task_id, category, quantity, price_version | Append-only billable usage |
| audit_index | audit_id, tenant_id, actor, action, resource, object_ref | Searchable index over immutable evidence |

### Rules

- Every tenant-owned row includes `tenant_id`; row-level security is defense in depth, not a substitute for service authorization.
- Use time-sortable UUIDs, UTC timestamps, explicit state-transition constraints, optimistic concurrency versions, and soft deletion only where policy requires recovery.
- Partition high-volume event and ledger tables by time and tenant hash; archive closed partitions to object storage.
- Read replicas serve projections and administration. Primary reads are mandatory for authorization, approvals, budgets, and workflow transitions.
- Backups are encrypted, point-in-time recoverable, routinely restored, region-bound, and covered by tenant deletion workflows.
- Source files, logs, model payloads, artifacts, and large event bodies live in encrypted object storage addressed by immutable IDs and checksums.

---

## 16. Vector database design

Use a managed, horizontally scalable vector service per region behind an internal Retrieval Index interface. Select a service that supports metadata filtering, namespaces, backups, predictable deletion, and private networking; validate Pinecone, Zilliz/Milvus, or an equivalent against measured workload.

- Namespace: tenant + repository + index generation. Dedicated enterprise tenants receive dedicated projects/collections.
- Vector record: item_id, content hash, embedding model/version, repository, commit lineage, path, symbol, language, ACL labels, classification, freshness.
- Separate collections by embedding model and content family; never mix incompatible dimensions or silently re-embed in place.
- Two-phase publication: write immutable generation, validate counts/recall/ACLs, atomically switch active pointer, retire old generation later.
- Hybrid lexical search resides in OpenSearch-class infrastructure or equivalent; reciprocal-rank fusion happens in Retrieval Service.
- Capacity model uses vectors per active repository tier, QPS, filter cardinality, replica factor, and re-index rate—not repository count alone.

---

## 17. Redis cache design

Redis is an acceleration and coordination layer, never the source of truth. Deploy one managed cluster per cell with TLS, ACLs, Multi-AZ, memory alarms, and explicit key ownership.

- Caches: tenant routing, authorization projections, repository metadata, retrieval results, model catalog, and short-lived task views.
- Coordination: rate-limit counters, idempotency windows, distributed leases, stream connection state, and fair-queue admission tokens.
- Keys begin with `environment:cell:tenant:domain:version`; sensitive values are encrypted or omitted.
- TTL plus event-driven invalidation; randomized expiry prevents stampedes. Single-flight and negative caching protect expensive misses.
- Eviction policy differs by cluster purpose; coordination keys must not share an evictable cache cluster at scale.
- No durable workflow state, audit evidence, billing ledger, or authoritative session membership in Redis.

---

## 18. Authentication

- Workforce identity uses OIDC/SAML SSO; lifecycle and group synchronization use SCIM. Consumer login may use OIDC/social providers without weakening enterprise controls.
- Browser sessions use secure, HttpOnly, SameSite cookies with rotation, CSRF protection, bounded lifetime, and step-up authentication for sensitive administration.
- Public APIs use OAuth 2.1 authorization code + PKCE, service accounts, and narrowly scoped personal tokens. Store only token hashes.
- Service-to-service identity uses workload identity and mTLS through the service mesh; no static cloud keys in workloads.
- Authorization combines RBAC for understandable roles with ABAC for tenant, repository, branch, environment, data class, network, time, task risk, and approval state.
- SCM permissions are checked at connect time and refreshed before protected operations. Installation tokens are minted just in time and held only in memory.
- Policy decisions return allow/deny, required approvals, redactions, budget, tool constraints, and a policy version included in audit evidence.

---

## 19. Security

### Platform and data

- Threat model covers prompt injection, malicious repositories, sandbox escape, poisoned dependencies, supply-chain compromise, credential theft, confused deputy, tenant crossover, and model-provider exposure.
- Encrypt in transit with TLS 1.3 where supported and at rest with envelope encryption. Enterprise tiers support customer-managed keys and crypto-shredding.
- Secrets remain in a cloud secret manager; agents receive scoped capability tokens or brokered operations, never raw long-lived credentials.
- Private endpoints isolate databases, caches, vector stores, model providers, and object storage. Default-deny egress is enforced in sandbox and service networks.
- Repository content is malware-scanned, secret-scanned, classified, and treated as untrusted. Executables are not run during indexing.

### Agent and supply chain

- Sandbox with microVM-grade isolation for untrusted execution, non-root users, read-only base images, seccomp/AppArmor, resource quotas, and disposable volumes.
- Tool outputs are bounded and labeled; content cannot grant permissions. High-risk actions require policy and human approval.
- Model contracts prohibit provider training and define retention; sensitive fields are redacted or routed to approved private endpoints.
- Build provenance, signed commits/tags, SBOMs, dependency pinning, image signing, admission verification, and SLSA-aligned pipelines protect delivery.
- Continuous controls include SAST, DAST, dependency/container/IaC scanning, secret detection, penetration tests, bug bounty, access reviews, and incident exercises.

### Hard boundary

A model never directly performs a side effect. It proposes an operation; deterministic services authenticate the actor, authorize scope, enforce policy and budget, execute through a constrained adapter, and write immutable evidence.

---

## 20. CI/CD

- Trunk-based development with short-lived branches and protected main.
- Stages: format/lint → unit/contract → security → integration → ephemeral environment → end-to-end → artifact attest.
- Build once; promote the signed immutable artifact through environments.
- Progressive delivery with canary by cell, automated SLO rollback, feature flags, and database expand/migrate/contract.
- Production changes require reviewed GitOps; emergency access is time-bound and audited.

---

## 21. Docker

- Minimal distroless runtime images, pinned digests, multi-stage builds, non-root UID, read-only filesystem.
- One process per container; configuration by environment and mounted secret references.
- Health endpoints distinguish startup, readiness, and liveness.
- SBOM and provenance attached to every image; sign with keyless workload identity.
- Separate hardened sandbox images from trusted platform service images.

---

## 22. Kubernetes

- Managed Kubernetes per cell; separate trusted services, indexing workers, and untrusted execution node pools.
- HPA for APIs, KEDA-class scaling for queue workers, cluster autoscaler for node pools.
- Pod security restricted, network policies default deny, workload identity, admission policy, quotas, topology spread.
- Priority classes protect gateway/workflow services from batch indexing.
- GitOps reconciles clusters; infrastructure modules create repeatable cells and disaster-recovery environments.

---

## 23. Monitoring

- OpenTelemetry traces, metrics, and logs propagate request, tenant hash, task, workflow, model call, tool call, and index generation IDs.
- Golden signals by service plus product SLIs: task start latency, success/abandon rate, index freshness, retrieval quality, approval wait, PR acceptance, cost per successful task.
- Multi-window burn-rate alerts page on SLO risk; symptom alerts outrank infrastructure noise.
- Cell dashboards expose saturation, noisy tenants, queue age, workflow stalls, model/provider health, sandbox capacity, and database/vector pressure.
- Synthetic tasks continuously test repository connect → index → agent → diff → PR in every region.
- Runbooks, ownership, incident command, status communication, postmortems, game days, backup restore, and cell evacuation are release requirements.

---

## 24. Logging

- Structured JSON logs with stable event names, severity, trace IDs, deployment version, region, cell, and pseudonymous tenant/task identifiers.
- Default deny for source, prompts, diffs, secrets, tokens, personal data, and tool payloads. Use references to encrypted artifacts when deep diagnostics are permitted.
- Application logs are operational and retention-limited; audit events are append-only, immutable, integrity-protected, and separately access-controlled.
- Audit schema records actor, delegated identity, action, resource, decision, policy version, capability, before/after references, result, and timestamp.
- Central SIEM receives normalized security events; tenant audit exports remain region-aware and support legal hold.
- Sampling is tail-aware: keep errors, security decisions, high-cost tasks, and slow traces; aggressively sample routine success.

---

## 25. Cost optimization

- Model router selects the least expensive model meeting a step’s quality, latency, context, residency, and tool-use requirements.
- Reserve strong models for planning, ambiguity, and review; use smaller models for classification, extraction, summarization, and reranking where evaluations prove parity.
- Prompt/context caching, semantic deduplication, hierarchical summaries, token budgets, and early-stop evaluators reduce repeated inference.
- Batch embeddings; deduplicate by content hash across snapshots within a tenant; re-embed only changed semantic units.
- Tier repositories by activity: hot indexes ready, warm indexes partially resident, cold indexes restored on demand with clear UX.
- Run interruptible indexing and evaluation on spot/preemptible capacity; keep workflow and interactive workloads on reliable pools.
- Per-tenant quotas, concurrency, daily/monthly budgets, anomaly detection, showback, and hard/soft limits prevent unbounded spend.
- Unit economics dashboard tracks cost per indexed GB, active repository, retrieval, agent minute, model token, and successful merged task.

---

## 26. Folder structure

Use a monorepo for platform contracts and coordinated delivery initially. Keep deployable boundaries explicit; do not share service database models or bypass service APIs.

```
alama/
├─ apps/                 web, API gateway/BFF, operator console
├─ services/             identity, repository, task, policy, retrieval, memory, usage
├─ workers/              indexing, agent runtime, evaluators, notifications
├─ gateways/             model providers, tools, SCM, issue trackers, CI
├─ platform/             workflow definitions, event schemas, shared observability
├─ contracts/            OpenAPI, protobuf, event and policy schemas
├─ packages/             narrow language libraries; no domain persistence sharing
├─ infra/                Terraform modules, regional cells, networks, managed data
├─ deploy/               Helm/Kustomize, GitOps environments, policy bundles
├─ security/             threat models, controls, data classifications, runbooks
├─ tests/                cross-service contract, integration, end-to-end, load, chaos
├─ evals/                agent, retrieval, safety, quality and cost benchmarks
├─ docs/                 ADRs, architecture, APIs, SLOs, operations
└─ tools/                developer CLI, generators, migration and release tooling
```

Each deployable unit contains owner metadata, README, API/event contracts, data migrations, unit tests, dashboards, alerts, runbook, threat-model delta, and deployment manifest.

---

## 27. Coding standards

- Prefer simple, explicit domain models; enforce dependency direction and module boundaries in CI.
- APIs and events are contract-first, versioned, backward compatible, bounded, and include idempotency semantics.
- No shared database access across services; schema ownership is singular and migrations are forward-compatible.
- Errors are typed and safe for clients; retries are declared, bounded, jittered, and limited to idempotent operations.
- All external calls set timeout, cancellation, circuit breaker, concurrency limit, and telemetry.
- Tests follow risk: unit for logic, contract for boundaries, integration for infrastructure, end-to-end for critical journeys, evaluation for probabilistic behavior.
- Model prompts, tools, retrieval strategies, and evaluators are versioned artifacts with offline and canary evaluation gates.
- Security-critical code requires two reviewers and named ownership; generated code follows the same gates.
- Feature flags have owners and expiry dates; operational configuration is validated and auditable.
- Definition of done includes docs, metrics, alert, runbook, capacity estimate, cost impact, privacy review, and rollback.

---

## 28. Development roadmap

| Phase | Timing | Scope | Exit criterion |
|---|---|---|---|
| 0 — Foundations | 0–6 weeks | Threat model, tenancy contract, ADRs, SLOs, cloud landing zone, identity, audit schema, event taxonomy. | Architecture review and disaster-recovery tabletop pass. |
| 1 — Controlled MVP | 6–14 weeks | GitHub integration, single-repo indexing, task workflows, sandboxed tools, one model provider, diff/test verification. | Internal users complete tasks with full replayable audit trail. |
| 2 — Production SaaS | 3–6 months | Regional cell, autoscaling workers, hybrid retrieval, budgets, billing ledger, observability, backups, SSO. | 99.9% execution SLO; load and recovery tests pass. |
| 3 — Enterprise | 6–10 months | SCIM, private connectivity, CMK, residency, policy packs, audit export, dedicated cells, GitLab/Bitbucket. | SOC 2 controls operating; first enterprise design partners live. |
| 4 — Global scale | 10–18 months | Multiple cells/regions, placement automation, cross-region control plane, 100k concurrency, tiered indexing. | Cell evacuation and region-failover game days pass. |
| 5 — Intelligence flywheel | 18+ months | Outcome learning, advanced evaluators, org knowledge graph, specialized agents, safe optimization. | Quality gains demonstrated without cross-tenant data leakage. |

---

## 29. Design decision trade-offs

Every fork below has more than one credible answer. Recommendations deliberately prefer operational clarity, security boundaries, contract stability, and reversible upgrades over the shortest path to a demo.

### Decision rubric

Prefer the option that:

1. keeps a hard security or tenancy boundary,
2. makes failure modes obvious,
3. localizes vendor churn behind an interface,
4. can be evaluated and rolled back, and
5. does not require heroic custom infrastructure unless that infrastructure is the product.

### Summary of recommended defaults

| Decision | Recommended default | Primary trade-off accepted |
|---|---|---|
| Tenancy | Shared cells + optional dedicated cells | Platform complexity over false simplicity of shared-everything |
| Control plane | Thin global + regional cells | Routing/placement work over late residency rewrites |
| Orchestration | Temporal-class workflows | New dependency over years of custom recovery code |
| Agent shape | Planner → executor → verifier | More contracts over unmaintainable mega-prompts |
| Sandbox | MicroVM-grade isolation | Density cost over catastrophic escape risk |
| Vectors | Managed service + internal interface | Unit cost over owning another database |
| Code graph | Materialized adjacency, not Neo4j-first | Shallower traversals over dual source-of-truth |
| Events | Kafka-class log + simple queues | Ops weight over non-replayable billing/audit |
| APIs | REST public + GraphQL BFF + gRPC internal | Multiple toolchains over one awkward style |
| Frontend | Modular monolith first | Module discipline over premature micro-frontends |
| Repo layout | Monorepo with deployable packages | CI tooling over cross-repo version skew |
| Policy | Central OPA/Cedar-class engine | Context schema work over scattered if/else auth |
| Identity | Managed IdP + BYO enterprise IdP | Vendor cost over building auth commodity |
| Cloud | Single primary cloud, portable interfaces | Concentration risk over multi-cloud tax |
| Memory | Governed knowledge objects | Write-gate friction over toxic transcript memory |
| Models | Mandatory Model Gateway | Critical-path service over SDK sprawl |
| Indexing | Incremental immutable generations | Pipeline complexity over full reindex economics |
| Redis | Cache/coordination only | Discipline over durability illusions |

---

### ADR-01: Multi-tenancy and blast-radius model

**Context:** Must support freemium SaaS density and regulated enterprises that demand isolation, residency, and predictable failure domains.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Shared services + shared DB with RLS only | Highest density, lowest early ops cost, simplest schema evolution. | One bug or migration can leak across tenants; hard to offer dedicated encryption, noisy-neighbor isolation, or per-customer evacuation. |
| B. Schema- or DB-per-tenant in one cluster | Stronger logical separation than RLS alone; easier per-tenant backup/delete. | Connection and migration explosion at millions of repos/tenants; operationally brittle before true scale. |
| C. Cell architecture: shared cell for most tenants, dedicated cell for enterprise | Bounded blast radius, regional residency, incremental scale-out, clear upgrade path to isolation without rewriting product APIs. | Higher platform complexity; placement, routing, and cell operations become first-class products. |
| D. Fully dedicated stack per customer from day one | Maximum isolation and customization. | Cannot economically serve millions of repositories; product divergence and ops toil destroy maintainability. |

**Recommend:** C — Cell architecture with shared multi-tenant cells and optional dedicated cells.

**Why:** Cells are the only model that scales density for the long tail while preserving a production path to enterprise isolation, residency, and evacuation without forking the codebase.

**Boundary:** Reject A as the end-state (acceptable only as an early internal prototype). Reject D unless selling only a tiny number of ultra-premium deployments.

---

### ADR-02: Global control plane vs single-region monolith

**Context:** Identity, billing, placement, and policy catalogs are global concerns; repository content and agent execution are not.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Single-region monolith for everything | Fastest to ship; one deploy story; simple debugging. | Residency and latency become rewrites later; blast radius is global; enterprise deals stall. |
| B. Fully active-active everywhere from day one | Best theoretical availability and locality. | Conflict resolution for identity, billing, and policy is extremely hard; premature distributed-systems tax. |
| C. Thin global control plane + regional data/execution cells | Separates rarely changing global metadata from high-volume tenant data; enables residency without dual-writing source code. | Requires careful placement and routing; control-plane outages must degrade gracefully. |

**Recommend:** C — Thin global control plane; keep repository bytes, indexes, workflows, and audit evidence cell-local.

**Why:** This boundary is expensive to retrofit. Designing it early preserves maintainability as regions and enterprise cells multiply.

**Boundary:** Do not build multi-master identity/billing (B) until a concrete multi-region consistency requirement forces it.

---

### ADR-03: Agent lifecycle orchestration

**Context:** Tasks run minutes to hours, wait on humans, retry after tool failures, and must resume after process death without losing auditability.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Queue + ad-hoc state machine in app DB | No new dependency; easy for short happy-path jobs. | Timers, human waits, compensation, versioned replay, and stuck-task recovery become custom distributed systems work forever. |
| B. Cloud Step Functions / similar managed state machines | Managed, visual, decent for linear pipelines. | Weak for long interactive agent loops, large payloads, local testing, and multi-cloud/portability; vendor lock-in in the hottest path. |
| C. Temporal-class durable workflow engine | First-class timers, signals, retries, deterministic replay, worker failover, code-as-workflow, strong operational tooling. | New skill set; must design workflow versioning and idempotent activities carefully. |
| D. Pure event-sourced saga only | Maximum flexibility and auditability. | Team rebuilds orchestration primitives Temporal already provides; higher long-term maintenance cost. |

**Recommend:** C — Temporal-class orchestration for task/agent lifecycle; Kafka for facts/metering/indexing fan-out.

**Why:** Agent work is inherently long-running and interruptible. Buying durability here prevents years of custom recovery bugs and makes production readiness measurable.

**Boundary:** Use A only for fire-and-forget side jobs (emails, non-critical notifications), never for the agent control loop.

---

### ADR-04: Agent runtime topology

**Context:** Quality, safety, and cost depend on whether planning, execution, and verification share one prompt or are separated.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Single monolithic agent loop | Simplest prompts and debugging early on. | Self-verification bias; hard to specialize models by step; one prompt becomes unmaintainable. |
| B. Fully autonomous multi-agent swarm with free messaging | Appealing for research demos and parallel exploration. | Non-deterministic coordination, cost explosions, difficult audits, and fragile production behavior. |
| C. Orchestrated planner → executor → verifier with typed handoffs | Clear ownership of steps, independent model routing, separate review prompts, replayable evidence, bounded parallelism. | More contracts and workflow states to maintain. |

**Recommend:** C — Deterministic orchestrator with specialized roles and typed artifacts between stages.

**Why:** Maintainability comes from explicit stage contracts, not from emergent agent chat. Safety and evaluation also attach naturally to stage boundaries.

**Boundary:** Reject B as a production default. Parallel specialist tools are fine; free-form agent-to-agent chatter is not.

---

### ADR-05: Untrusted code execution isolation

**Context:** Agents run customer repository code, package managers, tests, and potentially malicious content. Escape is a company-ending risk.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Same Kubernetes pod / sidecar as the agent worker | Fastest implementation and highest density. | Escape equals lateral movement into platform credentials; unacceptable for production AI coding. |
| B. Hardened containers with gVisor / Kata-like isolation | Better than plain containers; good density; Kubernetes-native. | Still shares more kernel attack surface than true VMs; maturity varies by workload. |
| C. MicroVM-grade sandbox per execution (Firecracker-class) | Strong isolation, fast boot relative to full VMs, clear security story for enterprises and insurers. | Higher platform investment; image and networking plumbing are non-trivial. |
| D. Full cloud VM per task | Familiar isolation boundary. | Slow cold start, poor density, expensive at 100k concurrency, painful for short tool calls. |

**Recommend:** C — MicroVM-grade isolation for repository execution; never run untrusted code in the trusted service plane.

**Why:** Long-term maintainability of trust is more valuable than short-term density. A clear hard boundary simplifies every later security review and enterprise questionnaire.

**Boundary:** A is forbidden in production. B may be an interim for trusted internal monorepos only, with a dated sunset.

---

### ADR-06: Vector index platform

**Context:** Need filtered ANN search, tenant namespaces, deletes, backups, private networking, and the ability to swap embedding models without rewriting product code.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. pgvector in primary PostgreSQL | One operational system; transactional simplicity; fine for small corpora. | Competes with OLTP for memory/IO; painful at millions of repos; upgrades and vacuum behavior become product risks. |
| B. Self-hosted Milvus / Qdrant / Weaviate | Control, potentially lower unit cost at extreme scale, rich features. | You own upgrades, backups, multi-tenant noisy neighbors, and paging—high permanent ops load. |
| C. Managed vector service behind an internal Retrieval Index interface | Faster path to production SLOs; vendor handles HA/scale; abstraction preserves exit option. | Unit cost and feature gaps; must validate deletion, filtering, and residency contracts. |
| D. Embeddings only in object storage + custom ANN | Maximum control. | Rebuilds a database; unacceptable maintainability for a startup unless vector search is the core product. |

**Recommend:** C — Managed regional vector service + hard internal abstraction; keep metadata and ACLs in PostgreSQL.

**Why:** Vector search is infrastructure, not differentiator. Paying for managed reliability while owning the interface maximizes production readiness and vendor portability.

**Boundary:** Use A only for tiny prototypes. Consider B only after a dedicated platform team and proven cost cliff on managed.

---

### ADR-07: Code graph and hybrid retrieval storage

**Context:** Agents need lexical precision, semantic recall, and structural navigation (callers, tests, ownership)—not chatty RAG alone.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Vector-only RAG | Simplest pipeline. | Misses exact symbols, renames, and structural relationships; quality plateaus quickly on large codebases. |
| B. Dedicated graph database (Neo4j-class) as system of record | Rich traversals and developer-friendly graph queries. | Another strongly consistent store to operate, back up, ACL, and keep commit-consistent with indexes; dual-write complexity. |
| C. Hybrid: OpenSearch-class lexical index + materialized adjacency + vectors | Uses proven stores for each access pattern; commit-versioned publications; good enough traversals for agent budgets. | Fusion logic lives in Retrieval Service; must invest in evaluation harnesses. |

**Recommend:** C — Hybrid retrieval with materialized code adjacency; defer a dedicated graph DB until traversal patterns outgrow SQL/adjacency lists.

**Why:** Most agent graph needs are shallow, budgeted expansions. Avoiding another source of truth preserves long-term operational maintainability.

**Boundary:** Adopt B only if deep multi-hop program analysis becomes a billed product feature with dedicated ownership.

---

### ADR-08: Async backbone

**Context:** Indexing, metering, audit, webhooks, and fan-out need durable, ordered, replayable streams with schema governance.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Cloud queues only (SQS / Pub/Sub) | Simple, cheap, serverless-friendly. | Weak replay, poor multi-consumer fan-out semantics, harder exactly-once-ish processing patterns for audit/metering. |
| B. Managed Kafka-class log | Replay, consumer groups, high throughput, mature schema/registry ecosystem, excellent for audit and usage ledgers. | Operationally heavier than queues; partition/key design matters. |
| C. Pulsar-class with tiered storage | Strong multi-tenancy and retention story. | Smaller hiring/ecosystem pool; higher uniqueness cost for most teams. |

**Recommend:** B — Managed Kafka-class for domain facts, audit, metering, and indexing; queues for simple push work.

**Why:** Replayability is non-negotiable for billing, audit reconstruction, and index rebuilds. Kafka’s ecosystem is the maintainable default.

**Boundary:** Do not put human-wait agent orchestration solely on Kafka; that belongs in the workflow engine.

---

### ADR-09: External and internal API styles

**Context:** Web, IDE, CLI, partners, and internal services have different aggregation and performance needs.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. One public GraphQL graph for everything | Flexible client fetching; popular with web teams. | Authorization complexity, noisy-neighbor queries, caching difficulty, awkward for partners and webhooks. |
| B. REST everywhere | Simple, cacheable, partner-friendly. | Web BFF aggregation becomes chatty without a composition layer. |
| C. REST/public resources + GraphQL/BFF for web + gRPC internal | Right tool per boundary; stable partner contracts; efficient service mesh calls; web gets aggregation without exposing internals. | Three contract toolchains to govern—manageable if contracts live in one repo. |

**Recommend:** C — Layered API strategy with contract-first schemas and a BFF that never leaks cell internals.

**Why:** Long-term maintainability comes from clear audience boundaries, not from forcing one style onto all clients.

**Boundary:** Avoid exposing raw GraphQL over internal microservice graphs to browsers.

---

### ADR-10: Frontend delivery architecture

**Context:** Task UX needs realtime streams, large diffs, and admin surfaces without fragmenting design and auth.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Micro-frontends from day one | Independent team deployability in theory. | Shared auth, design system, performance, and routing become distributed problems early; high coordination cost. |
| B. Modular monolith Next.js/React app + BFF | One auth/session story, coherent UX, simpler observability, faster cross-cutting changes. | Requires module discipline so the app does not become a ball of mud. |
| C. Separate SPA + unrelated admin apps with duplicated clients | Quick splits. | Contract drift and inconsistent task/review experiences. |

**Recommend:** B — Modular frontend monolith until multiple teams need independent release cadence proven by merge contention data.

**Why:** Premature micro-frontends optimize org charts, not maintainability. Enforce package boundaries and contract tests instead.

**Boundary:** Split only when build times, ownership conflicts, or release risk are measured—not anticipated.

---

### ADR-11: Codebase topology (mono vs poly)

**Context:** Platform contracts, workflow definitions, and evals must evolve together with services.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Polyrepo per service immediately | Clear ownership lines on paper. | Version skew across OpenAPI/protobuf/events; painful breaking changes; slow cross-cutting security fixes. |
| B. Application monorepo with explicit deployable packages | Atomic contract changes, shared CI policies, easier refactors, single security baseline. | Needs tooling for affected builds/tests; cultural discipline against improper imports. |
| C. Separate infra and app repos only | Different access controls for production credentials. | Still need strong contract packaging if services are split further. |

**Recommend:** B — Monorepo for apps/services/contracts/evals; keep secrets/infra state access tightly gated.

**Why:** Alama’s hardest bugs are contract and workflow mismatches. Atomic changes across boundaries beat distributed version hell.

**Boundary:** Extract a repo only for a truly independent product with a separate release train and SLA.

---

### ADR-12: Authorization and governance engine

**Context:** Need human-readable roles plus fine-grained rules over tools, models, branches, data class, and approvals.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Hard-coded if/else authorization in each service | Fast initially. | Divergent enforcement, untestable policy sprawl, audit nightmares. |
| B. Central Policy Service with OPA/Cedar-class engine + versioned bundles | Policy as data, dry-run, shared decision logs, progressive rollout of rules. | Requires disciplined input context schemas and decision caching. |
| C. Only IdP groups / coarse RBAC | Simple enterprise mental model. | Cannot express tool/model/budget/branch gates that AI platforms require. |

**Recommend:** B — RBAC for people + ABAC/policy engine for resources, tools, and agent actions.

**Why:** Agent platforms fail compliance reviews when authorization is scattered. Central decisions with versioned bundles are maintainable and auditable.

**Boundary:** Never let the model or prompt be the authorization system.

---

### ADR-13: Identity provider strategy

**Context:** Must support consumer signup and enterprise SSO/SCIM without owning a full IdP forever.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Build custom auth completely | Full control. | Security debt, MFA/SSO/SCIM/password reset become a product; poor maintainability. |
| B. Cognito/Auth0/Okta-class customer IdP + enterprise BYO IdP via SAML/OIDC | Mature protocols, SCIM ecosystem, faster compliance evidence. | Vendor cost; still need a clean internal subject model. |
| C. Enterprise-only SSO, no self-serve identity | Simpler security surface. | Blocks PLG growth and developer adoption. |

**Recommend:** B — Managed customer identity for self-serve; federate enterprise IdPs; keep Alama’s subject/entitlement model internal.

**Why:** Authentication commodity should be bought; authorization and tenancy semantics must remain owned product logic.

**Boundary:** Do not store IdP-specific identifiers as primary keys; map to stable internal subject IDs.

---

### ADR-14: Cloud and portability posture

**Context:** Enterprises ask about multi-cloud; engineering pay the tax.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Multi-cloud active from day one | Marketing checkbox; some regulated buyers like it. | Lowest common denominator services, doubled ops, slower features—classic premature optimization. |
| B. Single primary cloud, portable app contracts, IaC modules per cell | Deep use of managed services; faster production maturity; escape hatches via interfaces for DB/queue/workflow/vector. | Temporary concentration risk; acceptable if contracts are clean. |
| C. Kubernetes everywhere abstraction ignoring cloud services | Feels portable. | Reimplements databases/queues poorly; false portability. |

**Recommend:** B — One primary cloud first; portability at the application interface layer, not by avoiding managed services.

**Why:** Production readiness comes from operational excellence on one platform. Portability is an interface property, not a deployment-count property.

**Boundary:** Add a second cloud only for a funded enterprise commitment that pays for the duplicated cell operations.

---

### ADR-15: Long-term memory design

**Context:** Unbounded transcript storage looks smart until it leaks secrets, drifts, and pollutes future tasks.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Store full prompts/transcripts as memory | Trivial to implement. | PII/secret risk, prompt injection persistence, uncontrolled growth, low signal. |
| B. Vector-only memory without governance metadata | Easy semantic recall. | No provenance, expiry, ACL, or confidence; cannot meet enterprise deletion/legal hold. |
| C. Governed memory items: structured metadata in PostgreSQL + content artifacts + optional vectors | Scoped, typed, reviewable, expiring, attributable knowledge with deletion propagation. | Write path needs quality gates; more upfront design. |

**Recommend:** C — Memory as governed knowledge objects with explicit write gates.

**Why:** Maintainability and trust require that memory be a product with lifecycle, not a dump of model text.

**Boundary:** Never auto-promote raw tool output or untrusted README instructions into org semantic memory.

---

### ADR-16: LLM provider integration

**Context:** Models change monthly; enterprises constrain residency, training, and which vendors may see code.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Call provider SDKs directly from agent workers | Fastest demo. | Quotas, retries, redaction, routing, and accounting duplicate everywhere; lock-in spreads into domain code. |
| B. Central Model Gateway with provider adapters | One place for policy, fallback, tokenization accounting, prompt logging policy, and evaluation hooks. | Gateway becomes critical path—must be simple, highly available, and carefully versioned. |
| C. Only self-hosted open models | Maximum data control. | Quality/latency/ops gap for many coding tasks; still need a gateway for routing and metering. |

**Recommend:** B — Mandatory Model Gateway; workers speak only internal model contracts.

**Why:** Provider churn is certain. Encapsulating it is the highest-leverage maintainability decision in an AI platform.

**Boundary:** Self-hosted models are an option behind the same gateway, not a separate integration path.

---

### ADR-17: Repository indexing strategy

**Context:** Freshness, cost, and monorepo scale dominate unit economics.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Full re-index on every push | Simple correctness story. | Economically impossible at millions of repositories. |
| B. Incremental semantic-unit reindex with immutable index generations | Cost-efficient, rollback-friendly, commit-addressable, supports canary of embedding models. | Harder pipeline; needs manifest diffs and tombstones. |
| C. Lazy index only what the agent opens | Lowest idle cost. | First-task latency and missing structural context hurt quality; poor for enterprise expectations. |

**Recommend:** B — Eager incremental indexing for active repos; tier cold repos; publish immutable generations.

**Why:** Immutable generations make retrieval rollback and embedding upgrades safe—critical for long-term production operations.

**Boundary:** Use C only as a bootstrap for abandoned cold repositories after UX clearly discloses rebuild delay.

---

### ADR-18: Cache and coordination store

**Context:** Need low-latency limits, leases, and read-through caches without corrupting source of truth.

| Option | Strengths | Costs / risks |
|---|---|---|
| A. Redis as durable session/workflow store | Very fast. | Durability and audit lies; data loss under failover becomes user-visible corruption. |
| B. Redis for cache + ephemeral coordination; PostgreSQL/workflow engine own truth | Clear failure modes; cache can be flushed safely; coordination stays simple. | Requires discipline against “just put it in Redis”. |
| C. DynamoDB/Cosmos for all ephemeral coordination | Managed durability. | Higher latency and cost for hot rate-limit counters; still need a cache tier. |

**Recommend:** B — Redis strictly as acceleration/coordination; split cache clusters from lease/rate-limit clusters at scale.

**Why:** The maintainability win is semantic clarity under failure: losing Redis never loses tasks, audits, or entitlements.

**Boundary:** If a key cannot be regenerated from a system of record, it does not belong in Redis.

---

### Validation still required

Recommendations are defaults, not dogma. Before locking a vendor or runtime, run the listed rejection boundary and a concrete proof: escape test for sandboxes, restore drill for data stores, replay drill for workflows, recall/ACL test for retrieval, and load test for cell fair-queuing.

---

## 30. Definition of architectural success

Alama can safely execute a repository task, prove what context and authority it used, recover from component failure without losing task state, isolate one tenant or cell from another, and explain both quality and cost. Scale is achieved by adding cells and workers, not by weakening tenancy or bypassing governance. When speed and maintainability conflict, choose the design that a future team can operate, audit, and evolve without a rewrite.

### Recommended first step

Ratify the tenancy boundary, threat model, workflow state machine, data classification, and SLOs—then record the trade-off ADRs above—before selecting model or vector vendors. Those choices constrain every downstream component.

---

*End of document · Alama Reference Architecture v1.1*
