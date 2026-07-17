# Alama — Low-Level Design (LLD)
**Version 1.0** · Implementation Blueprint  
**Parent document:** `Alama-Production-Architecture-v1.1.md` (single source of truth for HLD decisions)  
**Audience:** Senior software engineers preparing to implement  
**Constraint:** No application source code in this document — contracts, schemas, modules, and behaviors only  
**Optimization criterion:** Long-term maintainability and production readiness

---

## Document control

| Field | Value |
|---|---|
| Bound HLD decisions | Cell tenancy, Temporal-class orchestration, Planner→Executor→Verifier, MicroVM sandbox, Model Gateway, managed vectors + hybrid retrieval, monorepo, Redis as cache/coordination only |
| Language defaults | Backend: Python 3.12+ (services/workers); Frontend: TypeScript + React; Contracts: OpenAPI 3.1 + Protobuf |
| API style | Public REST; Web BFF GraphQL (composition only); Internal gRPC |
| Identity | Managed IdP + enterprise SAML/OIDC; internal subject IDs |
| Workflow | Temporal-class; Kafka-class for facts/metering/indexing |
| Change process | Every LLD section maps to ADRs in HLD §29; deviations require a new ADR |

### Decision rubric (inherited)

Prefer designs that (1) keep hard security/tenancy boundaries, (2) make failure modes obvious, (3) hide vendor churn behind interfaces, (4) are evaluable and rollback-safe, (5) avoid custom infra unless it is the product.

---

## Table of contents

1. [System boundaries and layering](#1-system-boundaries-and-layering)
2. [Backend microservices](#2-backend-microservices)
3. [Dependency injection, exceptions, retries](#3-dependency-injection-exceptions-retries)
4. [Database design](#4-database-design)
5. [REST API catalog](#5-rest-api-catalog)
6. [AI system LLD](#6-ai-system-lld)
7. [Repository intelligence LLD](#7-repository-intelligence-lld)
8. [Memory system LLD](#8-memory-system-lld)
9. [RAG LLD](#9-rag-lld)
10. [Frontend LLD](#10-frontend-lld)
11. [Infrastructure LLD](#11-infrastructure-lld)
12. [Observability LLD](#12-observability-lld)
13. [Security LLD](#13-security-lld)
14. [Folder structure](#14-folder-structure)
15. [Testing strategy](#15-testing-strategy)
16. [Coding standards](#16-coding-standards)
17. [Implementation readiness checklist](#17-implementation-readiness-checklist)

---

## 1. System boundaries and layering

### 1.1 Clean Architecture + DDD mapping

| Layer | Allowed contents | Forbidden |
|---|---|---|
| **Domain** | Entities, value objects, aggregates, domain events, domain services, repository *interfaces* | Framework imports, HTTP, SQL, LLM SDKs |
| **Application** | Use cases / command handlers, DTOs, ports, workflow activity *interfaces*, transaction boundaries | Direct provider SDKs, UI concerns |
| **Adapters (inbound)** | REST/gRPC controllers, webhook receivers, Temporal activities wrappers, GraphQL BFF resolvers | Business rules |
| **Adapters (outbound)** | PostgreSQL repos, Redis, Kafka producers, vector client, SCM clients, Model Gateway client, sandbox RPC | Domain logic |
| **Composition root** | DI wiring per deployable | Shared mutable globals |

### 1.2 Bounded contexts (DDD)

| Context | Aggregate roots | Owns data |
|---|---|---|
| Identity & Access | `Tenant`, `Subject`, `RoleBinding` | Identity DB |
| Repository Ops | `RepositoryConnection`, `RepoSnapshot`, `WebhookDelivery` | Repository DB |
| Task Execution | `Task`, `Approval`, `TaskEvent` | Task DB |
| Agent Orchestration | `AgentRun` (workflow state externalized to Temporal) | Temporal + task projections |
| Knowledge & Memory | `MemoryItem`, `ConversationThread` | Knowledge DB |
| Indexing & Retrieval | `IndexGeneration`, `SymbolNode`, `RetrievalQuery` (query is ephemeral) | Index metadata in PG; vectors external |
| Policy & Governance | `PolicyBundle`, `PolicyDecision` | Policy DB / object store |
| Usage & Billing | `UsageRecord`, `Budget` | Usage ledger |
| Audit | `AuditEvent` | Append-only store + index |

**Cross-context rule:** No shared tables. Integration only via versioned APIs/events with `tenant_id`, `trace_id`, `schema_version`.

### 1.3 Deployable units (microservices)

| Service | Port (local) | Runtime | DB schema |
|---|---|---|---|
| `api-gateway` | 8080 | Stateless edge | none |
| `bff-web` | 8081 | GraphQL composition | none |
| `identity-service` | 8101 | Sync API | `identity` |
| `repository-service` | 8102 | Sync + webhooks | `repository` |
| `task-service` | 8103 | Sync + projections | `task` |
| `policy-service` | 8104 | Sync decisions | `policy` |
| `retrieval-service` | 8105 | Sync retrieval | `index_meta` (read) |
| `knowledge-service` | 8106 | Sync memory APIs | `knowledge` |
| `model-gateway` | 8107 | Sync LLM proxy | none (ledger via Kafka) |
| `tool-gateway` | 8108 | Sync tool broker | none |
| `audit-service` | 8109 | Ingest + query | `audit` |
| `usage-service` | 8110 | Metering + budgets | `usage` |
| `notification-service` | 8111 | Async delivery | `notification` |
| `indexing-worker` | n/a | Queue consumer | writes `index_meta` |
| `agent-worker` | n/a | Temporal worker | none (uses ports) |
| `evaluator-worker` | n/a | Batch/async | eval stores |

---

## 2. Backend microservices

For each service: responsibility, modules, primary classes/interfaces, inbound/outbound ports.

### 2.1 `api-gateway`

**Responsibility:** TLS termination (behind ingress), JWT/OIDC validation, tenant routing to home cell, request ID injection, rate limiting, body size limits, WAF integration, route to cell services. No business authorization beyond token validity and coarse quotas.

| Module | Purpose |
|---|---|
| `authn` | Validate JWT / session cookie bridge |
| `routing` | Resolve `tenant_id` → cell base URL |
| `ratelimit` | Hierarchical limits (IP, subject, tenant) |
| `proxy` | Reverse proxy with timeout/deadline propagation |
| `health` | Liveness/readiness |

| Type | Kind | Purpose |
|---|---|---|
| `TokenValidator` | Interface | Validate bearer/cookie → `Principal` |
| `TenantRouter` | Interface | Map tenant → cell endpoint |
| `RateLimiter` | Interface | Check and increment counters |
| `GatewayMiddleware` | Class | Compose auth → route → limit → proxy |
| `Principal` | Value object | `subject_id`, `tenant_ids`, `scopes`, `session_id` |

### 2.2 `bff-web`

**Responsibility:** GraphQL schema for web aggregation only. Calls cell REST/gRPC. Shapes DTOs for UI. Never exposes internal IDs of vendors or raw model payloads.

| Module | Purpose |
|---|---|
| `schema` | GraphQL types for Task, Repo, Memory, Usage |
| `dataloaders` | Batch N+1 prevention |
| `auth_context` | Forward principal + tenant |
| `mappers` | Service DTO → GraphQL types |

| Type | Kind | Purpose |
|---|---|---|
| `TaskResolver` | Class | Task queries/mutations |
| `RepositoryResolver` | Class | Repo listing/detail |
| `ChatResolver` | Class | Conversation + stream handshake |
| `ServiceClients` | Interface aggregate | Typed clients to task/repo/knowledge |

### 2.3 `identity-service`

**Responsibility:** Tenants, subjects, memberships, role bindings, SSO/SCIM projections, API keys (hashed), session metadata references. External IdP remains authentication source of truth.

| Module | Purpose |
|---|---|
| `domain` | `Tenant`, `Subject`, `Membership`, `ApiKey` |
| `application` | Create tenant, invite, bind roles, SCIM sync |
| `adapters.http` | REST controllers |
| `adapters.persistence` | PostgreSQL |
| `adapters.idp` | SCIM/OIDC admin hooks |

| Type | Kind | Purpose |
|---|---|---|
| `TenantRepository` | Interface | Persist tenants |
| `SubjectRepository` | Interface | Persist subjects |
| `MembershipService` | Domain service | Enforce single-home-cell membership rules |
| `ApiKeyService` | Application | Issue/rotate/revoke hashed keys |
| `ScimSyncHandler` | Application | Upsert users/groups from IdP |
| `CreateTenantHandler` | Use case | Provision tenant + default roles + cell placement request |

### 2.4 `repository-service`

**Responsibility:** SCM installations, repository connections, webhook intake, ref/snapshot intents, permission refresh, clone credentials *references* (never raw secrets).

| Module | Purpose |
|---|---|
| `domain` | `RepositoryConnection`, `Installation`, `WebhookDelivery`, `RepoSnapshot` |
| `application` | Connect, disconnect, reconcile, request snapshot |
| `adapters.scm` | GitHub/GitLab/Bitbucket adapters behind `ScmProvider` |
| `adapters.webhooks` | Signature verify, dedupe, outbox |
| `adapters.persistence` | PostgreSQL + object refs |

| Type | Kind | Purpose |
|---|---|---|
| `ScmProvider` | Interface | Normalize provider operations |
| `GithubScmAdapter` / `GitlabScmAdapter` / `BitbucketScmAdapter` | Classes | Provider-specific |
| `WebhookIngestor` | Application | Verify → dedupe → outbox event |
| `SnapshotRequestService` | Application | Enqueue indexing snapshot |
| `PermissionRefreshService` | Application | Refresh SCM ACL cache projection |
| `RepositoryRepository` | Interface | Persistence |
| `SecretRef` | Value object | Points to secret manager path only |

### 2.5 `task-service`

**Responsibility:** Task CRUD, state projection, approvals, event stream projection, cancel/pause signals to Temporal, budget attachment.

| Module | Purpose |
|---|---|
| `domain` | `Task`, `Approval`, `TaskEvent` |
| `application` | Create task, approve, cancel, list events |
| `adapters.workflow` | Start/signal Temporal workflows |
| `adapters.persistence` | Task DB |
| `adapters.stream` | SSE/WebSocket projection feed |

| Type | Kind | Purpose |
|---|---|---|
| `TaskAggregate` | Aggregate | State machine: `queued→planning→executing→verifying→awaiting_approval→completed|failed|cancelled` |
| `TaskRepository` | Interface | Persist tasks |
| `TaskWorkflowPort` | Interface | Start/signal/query workflow |
| `ApprovalService` | Application | Record human decision; signal workflow |
| `TaskEventProjector` | Application | Append ordered events; externalize large payloads |
| `CreateTaskHandler` | Use case | Validate policy + budget → start workflow |

**Task state transitions (authoritative):**

| From | To | Trigger |
|---|---|---|
| `queued` | `planning` | Workflow started |
| `planning` | `executing` | Plan accepted / auto |
| `executing` | `verifying` | Executor finished step batch |
| `verifying` | `executing` | Verifier requests more work |
| `verifying` | `awaiting_approval` | Policy gate |
| `awaiting_approval` | `executing` / `cancelled` | Human decision |
| `*` | `cancelled` | Cancel signal |
| `verifying` | `completed` | Success criteria met |
| `*` | `failed` | Exhausted retries / budget / fatal |

### 2.6 `policy-service`

**Responsibility:** Load versioned policy bundles; evaluate allow/deny/approval-required for tools, models, repos, branches, data class, budgets.

| Module | Purpose |
|---|---|
| `domain` | `PolicyBundle`, `PolicyDecision` |
| `engine` | OPA/Cedar-class evaluator wrapper |
| `application` | Evaluate, dry-run, activate version |
| `adapters.bundle_store` | Object storage for immutable bundles |

| Type | Kind | Purpose |
|---|---|---|
| `PolicyEngine` | Interface | `evaluate(input) → PolicyDecision` |
| `PolicyBundleRepository` | Interface | Versioned bundles |
| `EvaluatePolicyHandler` | Use case | Admission + tool-time evaluation |
| `PolicyDecision` | Value object | `effect`, `required_approvals[]`, `constraints`, `policy_version`, `reasons[]` |

### 2.7 `retrieval-service`

**Responsibility:** Hybrid retrieval (lexical + vector + symbol + graph expansion), ACL filter, fusion, rerank, citation packing. Commit-consistent.

| Module | Purpose |
|---|---|
| `query` | Query formulation / multi-query |
| `search` | Parallel candidate generators |
| `fusion` | RRF fusion |
| `expand` | Graph expansion within budget |
| `rerank` | Cross-encoder / model rerank via Model Gateway |
| `pack` | Context packing + citations |

| Type | Kind | Purpose |
|---|---|---|
| `RetrievalPort` | Interface | Public retrieve API |
| `LexicalSearchPort` | Interface | OpenSearch-class |
| `VectorSearchPort` | Interface | Managed vector |
| `SymbolLookupPort` | Interface | Symbol index |
| `GraphExpandPort` | Interface | Adjacency expansion |
| `RerankerPort` | Interface | Score candidates |
| `HybridRetriever` | Application service | Orchestrates pipeline |
| `EvidenceItem` | Value object | id, path, lines, commit, score, trust_label |

### 2.8 `knowledge-service`

**Responsibility:** Governed memory items, conversation threads, write gates, retention, deletion propagation.

| Module | Purpose |
|---|---|
| `domain` | `MemoryItem`, `Conversation`, `Message` |
| `writegate` | PII/secret/dedupe/confidence/policy |
| `application` | CRUD, search, promote candidates |
| `adapters.vector` | Optional semantic index via Retrieval Index interface |

| Type | Kind | Purpose |
|---|---|---|
| `MemoryWriteGate` | Domain service | Enforce promotion rules |
| `MemoryRepository` | Interface | Metadata persistence |
| `MemoryContentStore` | Interface | Encrypted object payloads |
| `ConversationService` | Application | Thread + message lifecycle |
| `RetentionJob` | Worker hook | Expiry + legal hold respect |

### 2.9 `model-gateway`

**Responsibility:** Only path to LLM/embedding providers. Routing, fallback, quotas, redaction policy, token accounting events, prompt template rendering hooks.

| Module | Purpose |
|---|---|
| `router` | Model selection by capability/cost/residency |
| `providers` | Adapters (OpenAI-class, Anthropic-class, Azure, self-host) |
| `policy` | Training prohibition, retention, field redaction |
| `accounting` | Emit usage events |
| `templates` | Named prompt template registry (versioned) |

| Type | Kind | Purpose |
|---|---|---|
| `ModelGateway` | Interface | `complete`, `embed`, `rerank` |
| `ProviderAdapter` | Interface | Vendor SDK isolation |
| `ModelRouter` | Class | Choose model for `ModelRequest` |
| `PromptTemplateRegistry` | Interface | Fetch immutable template by name+version |
| `UsageEmitter` | Interface | Kafka usage records |
| `RedactionFilter` | Class | Strip secrets before egress |

### 2.10 `tool-gateway`

**Responsibility:** Issue short-lived capabilities; authorize tool calls via Policy; invoke sandbox RPC; bound outputs; audit every call.

| Module | Purpose |
|---|---|
| `capabilities` | Mint/verify capability tokens |
| `catalog` | Tool schemas (read_file, apply_patch, run_tests, …) |
| `policy_bridge` | Call policy-service |
| `sandbox` | RPC to MicroVM executor |
| `audit` | Emit tool receipts |

| Type | Kind | Purpose |
|---|---|---|
| `ToolGateway` | Interface | `invoke(tool, args, capability)` |
| `CapabilityIssuer` | Interface | Mint scoped JWT-like capability |
| `SandboxExecutor` | Interface | Run in isolated VM |
| `ToolSchemaRegistry` | Class | JSON Schema per tool |
| `ToolReceipt` | Value object | Inputs hash, outputs ref, duration, policy_version |

**Hard rule:** Agent workers never hold SCM or cloud credentials. They only hold capabilities minted for a specific task + tool + TTL.

### 2.11 `audit-service`

**Responsibility:** Append-only normalized audit events; integrity protection; search index; export; legal hold.

| Type | Kind | Purpose |
|---|---|---|
| `AuditIngestor` | Application | Validate schema → Kafka → object store |
| `AuditQueryService` | Application | Tenant-scoped search |
| `AuditExporter` | Application | Region-aware export packages |
| `IntegrityHasher` | Domain | Hash chain / Merkle batch |

### 2.12 `usage-service`

**Responsibility:** Consume usage ledger events; budgets; hard/soft limits; showback; anomaly flags.

| Type | Kind | Purpose |
|---|---|---|
| `UsageIngestor` | Application | Idempotent ledger append |
| `BudgetService` | Application | Check/reserve/commit budget |
| `AnomalyDetector` | Application | Spike detection per tenant |

### 2.13 `notification-service`

**Responsibility:** Email, Slack/Teams, webhooks, in-app notifications. Template rendering. Delivery retries.

| Type | Kind | Purpose |
|---|---|---|
| `Notifier` | Interface | Channel send |
| `NotificationDispatcher` | Application | Route by preference |
| `DeliveryAttemptRepository` | Interface | Track attempts |

### 2.14 `indexing-worker`

**Responsibility:** Snapshot → classify → parse → enrich → chunk → embed → publish index generation. Incremental diffs.

| Type | Kind | Purpose |
|---|---|---|
| `IndexingPipeline` | Application orchestrator | Stages 1–8 from HLD |
| `TreeSitterParser` | Adapter | AST/symbols |
| `Chunker` | Domain service | Semantic unit chunking |
| `Embedder` | Port → Model Gateway | Batch embeddings |
| `IndexPublisher` | Application | Two-phase publish |
| `IncrementalDiffEngine` | Domain | Manifest diff + reverse deps |

### 2.15 `agent-worker` (Temporal worker)

**Responsibility:** Host Temporal activities for planner, executor, verifier, reviewer, tester, security, documentation, memory writer, recovery. No direct side effects outside Tool/Model gateways.

| Type | Kind | Purpose |
|---|---|---|
| `AgentWorkflow` | Workflow definition | Durable control loop |
| `PlanActivity` | Activity | Call Planner agent |
| `ExecuteStepActivity` | Activity | Call Coder/Executor via tools |
| `VerifyActivity` | Activity | Tester + Reviewer + Security checks |
| `ReflectActivity` | Activity | Reflection / replanning |
| `RecoverActivity` | Activity | Failure classification |
| `ContextBuilder` | Application | Assemble working memory + retrieval |
| `AgentMessageBus` | Internal protocol | Typed handoffs between roles (in-process artifacts, not free chat) |

### 2.16 `evaluator-worker`

**Responsibility:** Offline/online eval jobs for retrieval recall, agent success, safety, cost. Writes scorecards; never blocks hot path except canary gates.

---

## 3. Dependency injection, exceptions, retries

### 3.1 DI strategy

**Recommendation:** Constructor injection via a composition-root container per deployable (e.g., dependency-injector / wired FastAPI lifespan). No service locator in domain/application.

| Rule | Detail |
|---|---|
| Lifetimes | `Singleton`: clients, registries, engines. `Scoped` (request/workflow): UoW, principal. `Transient`: pure handlers |
| Interfaces | All outbound I/O behind ports in application layer |
| Config | Typed settings objects from env/ConfigMap; validated at boot |
| Testing | Swap adapters with fakes; domain tests need zero container |
| Forbidden | Importing concrete adapters from domain; ambient `get_current_tenant()` without explicit context param in new code |

**Trade-off:** Manual wiring is clearer for tiny services; a DI container scales better across 15+ services. **Choose container + explicit composition roots** for maintainability.

### 3.2 Exception model

| Exception type | HTTP | Retryable | Notes |
|---|---|---|---|
| `ValidationError` | 400 | No | Schema/business input |
| `AuthenticationError` | 401 | No | Missing/invalid token |
| `AuthorizationError` | 403 | No | Policy deny |
| `NotFoundError` | 404 | No | Missing resource in tenant |
| `ConflictError` | 409 | No | Version conflict / duplicate |
| `PreconditionFailed` | 412 | No | Stale index / wrong state |
| `RateLimitedError` | 429 | Yes (client) | Include `Retry-After` |
| `BudgetExceededError` | 402 or 429 | No | Product choice: **429 + `budget_exceeded` code** for API uniformity |
| `DependencyTransientError` | 503 | Yes | DB/Kafka/provider blip |
| `DependencyFatalError` | 502 | No | Misconfiguration |
| `SandboxError` | 500 mapped to task fail | Conditional | Classify escape vs tool fail |
| `DomainInvariantError` | 422 | No | Aggregate rule broken |

**Error response envelope (all APIs):**

```
{
  "error": {
    "code": "string_stable_code",
    "message": "safe_human_message",
    "details": {},
    "request_id": "uuid",
    "trace_id": "otel_trace"
  }
}
```

Never include stack traces, SQL, prompts, or source snippets in client errors.

### 3.3 Retry policies

| Operation class | Policy | Max attempts | Backoff | Jitter | Idempotency |
|---|---|---|---|---|---|
| HTTP inbound handler | No auto-retry (client responsibility) | — | — | — | Require `Idempotency-Key` on creates |
| Outbound HTTP/gRPC transient | Retry | 3 | Exp 100ms→2s | Full | Idempotent verbs / keys |
| Kafka consumer | Retry then DLQ | 5 | Exp | Yes | Inbox table by `event_id` |
| Temporal activity | Temporal retry options | Per activity | Exp | Yes | Activity idempotency key = `task_id:step_id:attempt_bucket` |
| Model Gateway | Retry + fallback model | 2 then fallback | Exp | Yes | Same `request_id` |
| Tool invoke | Retry only safe/read tools | 2 | Linear | Yes | Writes require idempotency token |
| Embedding batch | Retry | 5 | Exp | Yes | Content-hash dedupe |
| Notification | Retry | 8 | Exp up to 1h | Yes | Delivery id |

**Circuit breaker:** Per dependency (provider, SCM, vector). Open after N failures in window; half-open probe. Emit metric `dependency_circuit_state`.

**Deadline propagation:** Every request carries absolute deadline; activities honor remaining time; never retry past deadline.

---

## 4. Database design

### 4.1 Physical strategy

| Decision | Choice | Rationale |
|---|---|---|
| Engine | Managed PostgreSQL 16+ per cell | HLD default |
| Split | Separate databases: `identity`, `repository`, `task`, `knowledge`, `index_meta`, `policy`, `usage`, `audit`, `notification` | Blast radius + independent scaling |
| Multi-tenancy | `tenant_id` on every tenant row + RLS as defense in depth | Service auth remains primary |
| IDs | UUIDv7 (time-sortable) | Index locality |
| Time | `timestamptz` UTC | Mandatory |
| Soft delete | `deleted_at` only where recovery required; hard delete for secrets/PII when policy demands | See §4.8 |
| Migrations | Expand → migrate → contract; Squawk/liner in CI | Zero-downtime |

### 4.2 Common columns (convention)

Every tenant-owned table includes unless noted:

| Column | Type | Notes |
|---|---|---|
| `id` | `uuid` PK | UUIDv7 |
| `tenant_id` | `uuid` NOT NULL | Indexed; FK to tenants where same DB |
| `created_at` | `timestamptz` NOT NULL | Default `now()` |
| `updated_at` | `timestamptz` NOT NULL | Trigger maintained |
| `version` | `int` NOT NULL | Optimistic concurrency |
| `deleted_at` | `timestamptz` NULL | Soft delete where enabled |
| `created_by` | `uuid` NULL | Subject |
| `updated_by` | `uuid` NULL | Subject |

### 4.3 Schema: `identity`

#### `tenants`
| Column | Type | Constraints |
|---|---|---|
| id | uuid | PK |
| slug | citext | UNIQUE |
| name | text | NOT NULL |
| home_region | text | NOT NULL |
| home_cell | text | NOT NULL |
| isolation_tier | text | `shared` \| `dedicated` |
| plan | text | NOT NULL |
| status | text | `active` \| `suspended` \| `pending_delete` |
| data_residency | text | NOT NULL |
| created_at / updated_at / version | … | common |

**Indexes:** `UNIQUE(slug)`; `INDEX(home_cell)`; `INDEX(status)`.

#### `subjects`
| Column | Type | Constraints |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | FK → tenants(id) |
| external_idp_sub | text | NOT NULL |
| email | citext | NULL |
| display_name | text | NULL |
| status | text | `active` \| `disabled` |
| … | common | |

**Indexes:** `UNIQUE(tenant_id, external_idp_sub)`; `INDEX(tenant_id, email)`.

#### `groups`, `group_members`, `role_bindings`
- `groups(id, tenant_id, name, …)` UNIQUE(tenant_id, name)
- `group_members(group_id, subject_id, …)` PK(group_id, subject_id); FK both
- `role_bindings(id, tenant_id, subject_id NULL, group_id NULL, role text, resource_scope jsonb, …)` CHECK one of subject/group set

#### `api_keys`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | FK |
| subject_id | uuid | FK |
| name | text | |
| key_prefix | text | Display only |
| key_hash | bytea | Argon2/bcrypt hash |
| scopes | text[] | |
| expires_at | timestamptz | NULL |
| revoked_at | timestamptz | NULL |
| last_used_at | timestamptz | NULL |

**Indexes:** `UNIQUE(key_prefix)` optional; `INDEX(tenant_id, subject_id)`.

### 4.4 Schema: `repository`

#### `scm_installations`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| provider | text | `github` \| `gitlab` \| `bitbucket` |
| external_installation_id | text | |
| account_login | text | |
| secret_ref | text | secret manager path |
| status | text | |
| … | common | |

**Indexes:** `UNIQUE(tenant_id, provider, external_installation_id)`.

#### `repositories`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| installation_id | uuid | FK → scm_installations |
| provider | text | |
| external_repo_id | text | |
| full_name | text | `org/name` |
| default_branch | text | |
| visibility | text | |
| size_tier | text | `hot` \| `warm` \| `cold` |
| last_synced_at | timestamptz | |
| … | common | |

**Indexes:** `UNIQUE(tenant_id, provider, external_repo_id)`; `INDEX(tenant_id, full_name)`; `INDEX(tenant_id, size_tier)`.

#### `webhook_deliveries`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| provider | text | |
| delivery_id | text | Provider delivery id |
| event_type | text | |
| payload_ref | text | Object storage |
| status | text | `received` \| `processed` \| `failed` |
| processed_at | timestamptz | |

**Indexes:** `UNIQUE(provider, delivery_id)`; `INDEX(status, created_at)`.

#### `repo_snapshots`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| repository_id | uuid | FK → repositories |
| commit_sha | char(40) | |
| parent_commit_sha | char(40) | NULL |
| manifest_ref | text | Object storage |
| index_generation_id | uuid | NULL until published |
| state | text | `pending` \| `indexing` \| `ready` \| `failed` |
| error_code | text | NULL |
| … | common | |

**Indexes:** `UNIQUE(repository_id, commit_sha)`; `INDEX(repository_id, state)`; `INDEX(tenant_id, created_at DESC)`.

**FK:** `repositories.installation_id → scm_installations.id`; `repo_snapshots.repository_id → repositories.id`.

### 4.5 Schema: `task`

#### `tasks`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| repository_id | uuid | Logical FK (cross-DB: no PG FK; enforced in app) |
| created_by | uuid | Subject |
| title | text | |
| objective | text | |
| state | text | See state machine |
| workflow_id | text | Temporal workflow id |
| run_id | text | Temporal run id |
| base_commit_sha | char(40) | |
| branch_name | text | NULL |
| pr_url | text | NULL |
| budget_tokens | bigint | |
| budget_usd_micros | bigint | |
| policy_version | text | |
| priority | int | Default 0 |
| parent_task_id | uuid | NULL |
| … | common | |

**Indexes:** `INDEX(tenant_id, state, created_at DESC)`; `INDEX(tenant_id, repository_id, created_at DESC)`; `UNIQUE(workflow_id)`; `INDEX(created_by, created_at DESC)`.

#### `task_events`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| task_id | uuid | FK → tasks |
| sequence | bigint | Monotonic per task |
| event_type | text | |
| payload_ref | text | NULL if small inline |
| payload_inline | jsonb | NULL if large |
| actor_type | text | `system` \| `agent` \| `user` |
| actor_id | text | |
| created_at | timestamptz | |

**Indexes:** `UNIQUE(task_id, sequence)`; `INDEX(tenant_id, created_at DESC)`.  
**Partitioning:** RANGE on `created_at` monthly + hash subpartition optional.

#### `approvals`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| task_id | uuid | FK |
| gate | text | e.g. `protected_branch_write` |
| status | text | `pending` \| `approved` \| `rejected` \| `expired` |
| requested_at | timestamptz | |
| decided_at | timestamptz | NULL |
| decided_by | uuid | NULL |
| policy_version | text | |
| reason | text | NULL |
| … | | |

**Indexes:** `INDEX(task_id, status)`; `INDEX(tenant_id, status, requested_at)`.

#### `outbox_events` (transactional outbox pattern; per service DB)
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| aggregate_type | text | |
| aggregate_id | uuid | |
| event_type | text | |
| payload | jsonb | |
| created_at | timestamptz | |
| published_at | timestamptz | NULL |

**Indexes:** `INDEX(published_at) WHERE published_at IS NULL`.

### 4.6 Schema: `knowledge`

#### `conversations`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| task_id | uuid | NULL |
| repository_id | uuid | NULL |
| title | text | |
| … | common | soft delete |

#### `messages`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| conversation_id | uuid | FK |
| role | text | `user` \| `assistant` \| `system` |
| content_ref | text | Encrypted object |
| token_estimate | int | |
| sequence | int | |
| … | | |

**Indexes:** `UNIQUE(conversation_id, sequence)`.

#### `memory_items`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| scope | text | `user` \| `repo` \| `org` \| `task` \| `reflection` |
| memory_type | text | See §8 |
| repository_id | uuid | NULL |
| subject_id | uuid | NULL |
| task_id | uuid | NULL |
| title | text | |
| content_ref | text | |
| content_hash | text | |
| provenance | jsonb | sources, evidence ids |
| confidence | real | 0–1 |
| acl | jsonb | |
| embedding_model | text | NULL |
| vector_ref | text | NULL |
| expires_at | timestamptz | NULL |
| legal_hold | boolean | Default false |
| status | text | `candidate` \| `active` \| `archived` \| `rejected` |
| … | common | soft delete |

**Indexes:** `INDEX(tenant_id, scope, status)`; `INDEX(tenant_id, repository_id, status)`; `INDEX(expires_at) WHERE deleted_at IS NULL`; `UNIQUE(tenant_id, content_hash) WHERE status = 'active'`.

### 4.7 Schema: `index_meta`

#### `index_generations`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| repository_id | uuid | |
| snapshot_id | uuid | |
| commit_sha | char(40) | |
| state | text | `building` \| `validating` \| `active` \| `retired` \| `failed` |
| embedding_model | text | |
| embedding_dim | int | |
| vector_namespace | text | |
| lexical_index_name | text | |
| stats | jsonb | counts, coverage |
| activated_at | timestamptz | NULL |
| … | | |

**Indexes:** Partial unique: one `active` per repository — `UNIQUE(repository_id) WHERE state = 'active'` (or pointer table).

#### `symbol_nodes`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| tenant_id | uuid | |
| repository_id | uuid | |
| generation_id | uuid | FK |
| language | text | |
| kind | text | function/class/module/… |
| name | text | |
| qualified_name | text | |
| path | text | |
| start_line / end_line | int | |
| content_hash | text | |
| … | | |

**Indexes:** `INDEX(generation_id, qualified_name)`; `INDEX(generation_id, path)`; `INDEX(repository_id, name)`.

#### `symbol_edges`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| generation_id | uuid | FK |
| src_symbol_id | uuid | FK |
| dst_symbol_id | uuid | FK |
| edge_type | text | `calls` \| `imports` \| `inherits` \| `tests` \| `references` |
| … | | |

**Indexes:** `INDEX(generation_id, src_symbol_id, edge_type)`; `INDEX(generation_id, dst_symbol_id, edge_type)`.

#### `dependency_packages`
| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| generation_id | uuid | |
| ecosystem | text | npm/pypi/maven/… |
| name | text | |
| version | text | |
| path | text | lockfile path |

**Indexes:** `INDEX(generation_id, ecosystem, name)`.

### 4.8 Schema: `policy`, `usage`, `audit`, `notification` (summary)

**policy.policy_bundles:** `id, tenant_id, version, bundle_ref, status(draft|active|retired), checksum, activated_at`  
UNIQUE(tenant_id, version); partial unique active per tenant.

**usage.usage_ledger:** `id, tenant_id, task_id NULL, category, quantity, unit, price_version, provider, model, created_at`  
Partition by month; INDEX(tenant_id, created_at); UNIQUE(idempotency_key).

**usage.budgets:** `id, tenant_id, period, limit_usd_micros, limit_tokens, soft_pct, hard_stop bool, spent_*`.

**audit.audit_index:** `id, tenant_id, actor_type, actor_id, action, resource_type, resource_id, decision, policy_version, object_ref, created_at`  
INDEX(tenant_id, created_at DESC); INDEX(tenant_id, action, created_at).

**notification.notifications:** delivery tracking tables with attempts.

### 4.9 Relationships (logical ER)

```
tenants 1──* subjects
tenants 1──* repositories
repositories 1──* repo_snapshots
repo_snapshots 1──0..1 index_generations (active pointer)
index_generations 1──* symbol_nodes
symbol_nodes 1──* symbol_edges (as src/dst)
tenants 1──* tasks
tasks 1──* task_events
tasks 1──* approvals
tasks 0..1──* conversations
tenants 1──* memory_items
tenants 1──* policy_bundles
tenants 1──* usage_ledger
```

Cross-database references (`tasks.repository_id` → `repositories.id`) are **application-enforced**, not PG FKs.

### 4.10 Migration strategy

1. All schema changes via versioned migration tool (Alembic/Flyway-class) per database.
2. **Expand:** add nullable columns/tables; deploy code that writes both old+new if needed.
3. **Migrate:** backfill job; verify counts.
4. **Contract:** remove old columns only after dual-read period + feature flag off.
5. Forbidden: rename-in-place destructive changes without expand/contract.
6. Each migration has: forward script, optional rollback *only* for non-data-destructive expands, owner, estimated lock time.
7. CI runs migrations against ephemeral Postgres; fails on exclusive locks on large tables without `CONCURRENTLY` indexes.

### 4.11 Soft deletes

| Entity | Soft delete? | Reason |
|---|---|---|
| tenants | Status machine + delayed hard delete | Legal/compliance |
| subjects | `disabled` status | Audit |
| repositories | soft | Undo disconnect |
| tasks | no soft; terminal states | Immutability of history |
| task_events | never delete | Audit |
| memory_items | soft + tombstone vectors | Retention |
| conversations/messages | soft | User delete UX |
| api_keys | `revoked_at` | Security |
| usage/audit | never soft-delete | Compliance |

Hard delete jobs respect `legal_hold` and emit audit events.

### 4.12 Auditing & versioning

- **Row versioning:** `version` column + `UPDATE … WHERE version = $expected`.
- **Policy/index/prompt templates:** immutable versions; activation pointer.
- **Domain audit:** every privileged action → `audit-service` (not only DB triggers).
- **DB triggers:** maintain `updated_at` only; do not implement business audit solely in triggers.

---

## 5. REST API catalog

Base URL: `https://api.{region}.alama.dev/v1`  
Auth: `Authorization: Bearer <access_token>` or API key  
Headers: `X-Request-Id`, `Idempotency-Key` (POST creates), `X-Tenant-Id` (if multi-tenant token)

### 5.1 Cross-cutting API rules

| Concern | Design |
|---|---|
| Pagination | Cursor-based: `?cursor=&limit=` (default 25, max 100). Response: `{ items, next_cursor }` |
| Rate limiting | Headers `X-RateLimit-Limit/Remaining/Reset`. 429 + `Retry-After` |
| Validation | JSON Schema / Pydantic at edge; domain re-validates |
| Idempotency | Stored 24h by hash(key + tenant + route + body hash) |
| Status codes | 200 OK, 201 Created, 202 Accepted (async), 204 No Content, 400/401/403/404/409/412/422/429/500/502/503 |

### 5.2 Identity

| Method | Path | Request | Response | Codes |
|---|---|---|---|---|
| GET | `/tenants/me` | — | Tenant | 200,401 |
| GET | `/subjects/me` | — | Subject + roles | 200,401 |
| GET | `/tenants/{tid}/subjects` | cursor | Subject[] | 200,403 |
| POST | `/tenants/{tid}/api-keys` | `{name,scopes,expires_at}` | `{id,key_once,prefix}` | 201,403,422 |
| DELETE | `/tenants/{tid}/api-keys/{id}` | — | 204 | 204,404 |

### 5.3 Repositories

| Method | Path | Request | Response | Codes |
|---|---|---|---|---|
| GET | `/repositories` | filters | Repo[] | 200 |
| GET | `/repositories/{id}` | — | Repo detail | 200,404 |
| POST | `/repositories/connect` | `{provider,installation_id,external_repo_id}` | Repo | 201,409 |
| DELETE | `/repositories/{id}` | — | 204 | 204 |
| POST | `/repositories/{id}/reindex` | `{ref?}` | `{snapshot_id}` 202 | 202,409 |
| GET | `/repositories/{id}/snapshots` | cursor | Snapshot[] | 200 |
| GET | `/repositories/{id}/index/status` | — | Index status | 200 |

Webhooks: `POST /webhooks/{provider}` — signature required; 202 always after accept.

### 5.4 Tasks

| Method | Path | Request | Response | Codes |
|---|---|---|---|---|
| POST | `/tasks` | `{repository_id,objective,title?,budget?,base_ref?}` | Task 201 | 201,402/429 budget,403 |
| GET | `/tasks` | filters | Task[] | 200 |
| GET | `/tasks/{id}` | — | Task | 200,404 |
| POST | `/tasks/{id}/cancel` | `{reason?}` | Task | 200,409 |
| POST | `/tasks/{id}/pause` | — | Task | 200,409 |
| POST | `/tasks/{id}/resume` | — | Task | 200,409 |
| GET | `/tasks/{id}/events` | cursor/from_seq | Event[] | 200 |
| GET | `/tasks/{id}/events/stream` | SSE | event-stream | 200 |
| GET | `/tasks/{id}/approvals` | — | Approval[] | 200 |
| POST | `/approvals/{id}/decide` | `{decision,reason?}` | Approval | 200,409,403 |

**Create task response (shape):** `id, state, repository_id, workflow_id, created_at, links.events_stream`

### 5.5 Retrieval & knowledge

| Method | Path | Request | Response | Codes |
|---|---|---|---|---|
| POST | `/retrieve` | `{repository_id,commit_sha?,query,task_id?,limit?}` | `{evidence[],citations[]}` | 200,412 stale |
| GET | `/memories` | filters | MemoryItem[] | 200 |
| POST | `/memories` | memory draft | MemoryItem | 201,422 |
| PATCH | `/memories/{id}` | patch | MemoryItem | 200 |
| DELETE | `/memories/{id}` | — | 204 | 204 |
| GET | `/conversations` | — | Conversation[] | 200 |
| POST | `/conversations` | `{task_id?,title?}` | Conversation | 201 |
| POST | `/conversations/{id}/messages` | `{content}` | Message + may 202 start task | 201/202 |

### 5.6 Policy, usage, audit

| Method | Path | Notes |
|---|---|---|
| POST | `/policy/evaluate` | Dry-run / debug (admin) |
| GET | `/policy/bundles` | List versions |
| POST | `/policy/bundles/{version}/activate` | Admin |
| GET | `/usage/summary` | Period aggregates |
| GET | `/usage/budgets` | Current budgets |
| GET | `/audit/events` | Cursor + filters; admin |

### 5.7 Model/Tool gateways (internal only)

Not public. Internal gRPC:

- `ModelGateway.Complete / Embed / Rerank`
- `ToolGateway.Invoke / MintCapability`
- `Sandbox.Exec`

---

## 6. AI system LLD

### 6.1 Agent roster (roles)

Aligned to HLD Planner→Executor→Verifier. Product names map as follows:

| Agent role | Alias in requirements | Primary duty | Typical model tier |
|---|---|---|---|
| Planner | Planner | Decompose objective → plan DAG with success criteria, risks, gates | Strong |
| Coder | Coder / Executor | Apply minimal diffs via tools; implement plan steps | Strong/mid |
| Reviewer | Reviewer | Independent review of diff vs objective/policy | Strong (prefer different family) |
| Tester | Tester | Select/run tests; interpret failures; propose fixes | Mid/strong |
| Security | Security | Secret/vuln/authz review of changes | Strong |
| Documentation | Documentation | Update docs/changelogs when required by plan | Mid |
| Memory Writer | Memory | Propose governed memory candidates | Mid |
| Recovery | Recovery | Classify failures; checkpoint rollback; escalate | Mid |
| Summarizer | — | User-facing timeline/PR description | Mid |

**Trade-off:** Separate role prompts vs one mega-agent. **Recommend separate roles with typed artifacts** (HLD ADR-04).

### 6.2 Agent communication protocol

Agents do **not** free-chat. They exchange versioned artifacts on the workflow state.

#### Message envelope

| Field | Type | Purpose |
|---|---|---|
| `artifact_id` | uuid | Stable id |
| `artifact_type` | enum | `Plan`, `StepResult`, `DiffBundle`, `TestReport`, `ReviewReport`, `SecurityReport`, `Reflection`, `MemoryCandidate`, `UserSummary` |
| `task_id` | uuid | |
| `producer_role` | enum | |
| `schema_version` | semver | |
| `created_at` | timestamptz | |
| `payload_ref` | object key | Large bodies in object store |
| `citations` | EvidenceRef[] | Required when claiming repo facts |
| `policy_version` | string | |

#### Allowed transitions

```
Planner → Plan
ContextBuilder → RetrievalPack (not an LLM role)
Coder → DiffBundle + StepResult
Tester → TestReport
Reviewer → ReviewReport
Security → SecurityReport
Recovery → Reflection + RecoveryAction
Memory Writer → MemoryCandidate
Summarizer → UserSummary
Verifier gate (deterministic) → continue | approve_wait | fail | complete
```

### 6.3 Planning algorithm

1. **Admit:** Policy + budget + repo ACL + index freshness check.
2. **Clarify (optional):** If objective underspecified, emit clarification questions (user wait) instead of guessing.
3. **Retrieve:** Hybrid retrieval pack for objective + repo conventions.
4. **Draft plan:** Planner produces ordered steps with: `goal`, `files_likely`, `tools_needed`, `risk`, `verification`, `approval_gates`, `stop_conditions`.
5. **Validate plan (deterministic):** Schema check; max steps; disallowed tools stripped; budget estimate.
6. **Optional plan approval:** If policy requires, wait on human.
7. **Execute loop:** For each ready step (dependency-respecting):
   - Build step context (working memory + targeted retrieve)
   - Coder invokes tools via Tool Gateway
   - Checkpoint workspace snapshot
   - Tester/Reviewer/Security as required by step tags
   - Reflection if failure
8. **Complete:** Summarizer + PR handoff + memory candidates through write gate.

**Planning output constraints:** max N steps (configurable, default 20); each step ≤ token budget; no step may request raw credentials.

### 6.4 Reflection loop

Triggered when: test fail, reviewer reject, tool error, policy deny soft, timeout partial.

| Step | Behavior |
|---|---|
| Observe | Compact failure evidence into Reflection artifact |
| Diagnose | Recovery agent classifies: env, wrong file, flaky test, bad plan, injection, budget |
| Decide | `retry_step` \| `replan` \| `narrow_scope` \| `rollback_checkpoint` \| `escalate_human` \| `fail_task` |
| Bound | Max reflections per task (default 5); max replans (default 2) |
| Record | Reflection Memory candidate (quality-gated) |

### 6.5 Tool invocation

1. Coder emits `ToolCallIntent{name, args, reason}` (not raw shell).
2. Agent worker asks Tool Gateway with task capability.
3. Tool Gateway: schema validate → Policy evaluate → mint/verify capability → sandbox RPC → bound output → ToolReceipt → audit.
4. Result returned as `ToolResult` artifact into working memory (size-capped; overflow to object ref).

**Tool catalog (MVP+):** `get_file`, `search_code`, `apply_patch`, `list_dir`, `run_tests`, `run_command` (allowlisted), `open_pr`, `read_ci`, `git_checkout` (sandbox only).

**Forbidden tools by default:** arbitrary network egress, cloud admin, secret read, force-push, prod deploy.

### 6.6 Failure recovery & retry strategy (AI-specific)

| Failure | Recovery |
|---|---|
| Model timeout/5xx | Model Gateway retry then fallback model; preserve same artifact schema |
| Invalid model JSON | Repair prompt once; then fail step |
| Tool timeout | Retry if read-only; else mark step failed → reflection |
| Sandbox OOM | Smaller batch / fewer tests; escalate if repeat |
| Patch conflict | Re-read files; rebase patch; max 2 |
| Tests fail | Tester proposes fix step; cap loops |
| Policy deny | If `approval_required` → wait; if hard deny → fail with reason |
| Prompt injection suspected | Quarantine retrieved text as untrusted; continue with citations only; security flag |

### 6.7 Task queue / workflow mapping

- **Queue abstraction:** Temporal task queues per cell: `agent-general`, `agent-highmem`, `index-default`, `index-bulk`.
- Fairness: tenant concurrency limits in workflow starter + worker permits.
- Priority: enterprise / SLA tenants mapped to higher Temporal priority keys if supported; else separate queues.

### 6.8 Prompt templates

Stored in versioned registry (object store + DB pointer), not in source string literals for production prompts.

| Template name | Used by | Inputs | Output schema |
|---|---|---|---|
| `planner.vN` | Planner | objective, repo summary, retrieval pack, policy constraints | Plan JSON |
| `coder.vN` | Coder | step, files, retrieval, prior failures | Tool intents / patch summary |
| `reviewer.vN` | Reviewer | diff, objective, standards | ReviewReport |
| `tester.vN` | Tester | diff, test map, failures | TestPlan / interpretation |
| `security.vN` | Security | diff, secret scan, deps | SecurityReport |
| `docs.vN` | Documentation | diff, doc paths | DocPatch plan |
| `reflect.vN` | Recovery | failure bundle | Reflection |
| `summarize.vN` | Summarizer | timeline artifacts | UserSummary |
| `memory_extract.vN` | Memory Writer | outcome | MemoryCandidate[] |

**Rules:** Templates immutable by version; canary via task %; eval gate before promotion; system policy section always prepended server-side (not model-editable).

---

## 7. Repository intelligence LLD

### 7.1 Pipeline stages (modules)

| Stage | Module/Class | Input | Output |
|---|---|---|---|
| Ingest | `WebhookIngestor` | SCM event | Outbox `RepoChanged` |
| Snapshot | `SnapshotService` | repo+ref | `repo_snapshots` + manifest object |
| Classify | `RepoClassifier` | file tree | languages, binaries, secrets hits, size_tier |
| Parse | `TreeSitterFacade` | source files | AST + symbols + edges |
| Enrich | `EnrichmentJoiner` | SCM metadata | owners, blame summary, CI |
| Chunk | `SemanticChunker` | symbols/docs | chunks + hierarchy summaries |
| Embed | `EmbeddingBatcher` | chunks | vectors via Model Gateway |
| Publish | `IndexPublisher` | all artifacts | active `index_generations` |

### 7.2 Tree-sitter & AST

- Language grammars pinned by version; loaded in parser workers.
- Unsupported languages: fallback to line-window chunking + lexical only; flag coverage metric.
- AST not stored wholesale; extract **symbol table** and **edges**; optionally store compact AST slices for complex files in object store by content hash.

### 7.3 Chunking strategy

| Content | Chunk unit | Overlap | Metadata |
|---|---|---|---|
| Code | Symbol (function/class) preferred | Parent header summary | path, symbol, lines, language, commit |
| Large symbol | Split by logical blocks with parent qualified_name | Small | parent_id |
| Markdown/docs | Section headings | 1 heading | path, heading path |
| Config | Whole file if small; else key sections | 0 | path, kind |
| Generated/vendor | Skip embed; lexical optional | — | classified skip |

Max chunk tokens configurable (default ~750–1200 tokens equivalent).

### 7.4 Embedding strategy

- Single embedding model per index generation; model name+dim stored on generation.
- Batch size tuned; dedupe by `content_hash` within tenant.
- Re-embed only changed semantic units on incremental update.
- Migration to new model = new generation + shadow eval + atomic switch (never in-place mutate).

### 7.5 Incremental indexing

1. Diff manifests between parent commit and new commit (path + content hash).
2. Invalidate chunks/symbols for changed paths; reparse.
3. Recompute reverse-adjacent edges for impacted symbols.
4. Tombstone removed paths in lexical+vector namespaces.
5. Build new generation (or patch generation with validation) → activate.
6. Freshness SLO: webhook→searchable < 2 min p95 for typical repos.

### 7.6 Graphs

| Graph | Storage | Edge types | Query use |
|---|---|---|---|
| Symbol graph | `symbol_nodes` / `symbol_edges` | calls, imports, inherits, references | Expand retrieval |
| Dependency graph | `dependency_packages` + file imports | depends_on | Supply chain + impact |
| Repository graph | logical: repos↔owners↔services (future) | owns, deploys | Enterprise nav |
| Cross references | edges + lexical anchors | references across files | Navigation |

**Trade-off:** Neo4j vs materialized adjacency — **materialized adjacency in PG** (HLD ADR-07).

---

## 8. Memory system LLD

### 8.1 Memory kinds

| Kind | Scope keys | Write path | Read path |
|---|---|---|---|
| Working Memory | `task_id` | Workflow state + compactors | ContextBuilder |
| Long-term Memory (org semantic) | `tenant_id` | Write gate + optional approval | Retrieval + knowledge API |
| User Memory | `tenant_id+subject_id` | Preferences/facts with consent | Personalization (policy-limited) |
| Repository Memory | `tenant_id+repository_id` | Index summaries + approved conventions | Retrieval boost |
| Conversation Memory | `conversation_id` | Messages content_ref | Chat UI + summarizer |
| Reflection Memory | `tenant_id` (+repo optional) | Quality-gated reflections | Planner hints |

### 8.2 Working memory structure

| Slot | Content | Cap |
|---|---|---|
| objective | User goal | fixed |
| plan | Current Plan artifact | 1 |
| step_cursor | Active step id | 1 |
| open_files | Path→summary | LRU N |
| tool_receipts | Recent receipts | last K |
| retrieval_pack | Evidence ids | token budget |
| constraints | Policy constraints | fixed |
| failure_buffer | Recent failures | last M |

Compaction: Summarizer/compactor activity when token estimate > threshold; preserve citations.

### 8.3 Summarization strategy

- Conversation: rolling summary every N messages + pin last U turns verbatim.
- Task timeline: incremental summaries per phase for UI.
- Repo: hierarchical module summaries refreshed on index generation.
- Never summarize away security findings or approval reasons.

### 8.4 Retention strategy

| Class | Default retention | Notes |
|---|---|---|
| Working | Task TTL + 7 days artifacts | Then cold object archive |
| Conversation | Tenant policy (e.g. 90–365d) | User delete supported |
| User memory | Until user/org delete | Exportable |
| Repo memory | Tied to repo connection | Deleted on disconnect after grace |
| Reflection | 180d candidate; promote or expire | |
| Audit | Longer (1–7y) immutable | Separate from memory |

Legal hold freezes expiry. Deletion propagates: PG row → object → vector tombstone → cache invalidate.

---

## 9. RAG LLD

### 9.1 Document ingestion

Sources: repository files (primary), approved docs URLs (optional), issue/PR text (optional, classified), memory items (scoped).

Ingestion always through indexing/knowledge pipelines — no ad-hoc embed from API without metadata.

### 9.2 Chunking / embedding / metadata

Reuse §7.3–7.4. Mandatory metadata on every vector:

`tenant_id, repository_id, generation_id, commit_sha, path, symbol, language, acl_labels, classification, content_hash, embedding_model, chunk_kind`.

### 9.3 Retrieval pipeline (implementation detail)

| Step | Implementation |
|---|---|
| Formulate | `QueryFormulator` → keyword + semantic + symbol queries |
| Authorize | Filter by principal ACL before search where possible; post-filter mandatory |
| Lexical | BM25/OpenSearch-class |
| Dense | Top-K ANN with metadata filters |
| Symbol | Exact/qualified name lookup |
| Fuse | Reciprocal Rank Fusion weights: symbol > lexical > dense (tunable) |
| Expand | ±1 hop edges budgeted (default 20 nodes) |
| Rerank | Cross-encoder via Model Gateway; diversity MMR optional |
| Pack | Token budget allocator; keep boundaries |
| Cite | Each used span → `Citation{evidence_id,path,start,end,commit,sha}` |

### 9.4 Hybrid search & reranking

- Hybrid is default for code tasks; pure dense only for natural-language docs.
- Rerank top 50 → top 12 (defaults).
- If commit not indexed: ancestor fallback only if policy allows; mark `stale=true`.

### 9.5 Citation generation

- Agents must attach `citations[]` when stating repo facts.
- Attribution evaluator samples tasks offline; online warning if unsupported claims exceed threshold.
- UI renders citations as clickable path:line links.

---

## 10. Frontend LLD

### 10.1 Application shell

- Framework: Next.js App Router + React + TypeScript
- Styling: design system tokens (existing brand when present)
- Data: TanStack Query; BFF GraphQL + REST for streams
- Auth: OIDC PKCE via BFF cookie session (HttpOnly)
- State: server state in Query cache; UI-local in Zustand/context sparingly
- Routing: App Router file routes below

### 10.2 Screens

| Screen | Route | Purpose | Key components |
|---|---|---|---|
| Login / SSO | `/login` | Auth entry | IdP buttons, error states |
| Dashboard | `/` | Tasks overview, repos health, budgets | `TaskList`, `UsageWidget`, `RepoStatus` |
| Repositories | `/repos` | Connected repos | Table, connect dialog |
| Repository page | `/repos/[repoId]` | Index status, snapshots, settings, recent tasks | `IndexStatus`, `SnapshotList`, `RepoTasks` |
| Issues / Tasks list | `/tasks` | Filterable tasks | Filters, state pills |
| Task detail / Issue page | `/tasks/[taskId]` | Timeline, plan, diffs, approvals | `Timeline`, `DiffViewer`, `ApprovalBanner` |
| Chat | `/chat` or `/tasks/[id]/chat` | Conversational entry to tasks | `MessageList`, `Composer`, stream |
| Approvals inbox | `/approvals` | Pending gates | Decide actions |
| Settings — Profile | `/settings/profile` | User prefs | Forms |
| Settings — Org | `/settings/org` | SSO, roles, policies | Admin only |
| Settings — Integrations | `/settings/integrations` | SCM, Slack | OAuth install flows |
| Settings — Billing/Usage | `/settings/usage` | Budgets, spend | Charts |
| Analytics | `/analytics` | Success rate, latency, cost | Dashboards (tenant) |
| Audit (admin) | `/admin/audit` | Audit search | Table + export |
| 403/404 | `/403`, `/404` | Errors | |

### 10.3 User flows

1. **Connect repo:** Settings → Integrations → OAuth → select repos → index job → Dashboard green.
2. **Start task from chat:** Chat → objective → create task → stream events → approval if needed → PR link.
3. **Start task from repo:** Repo page → New task → form → same as above.
4. **Approve gate:** Notification → Approvals → decide → workflow resumes.
5. **Review outcome:** Task page → diff → citations → open PR.

### 10.4 Routing & guards

- Middleware: session required for all except `/login`, health.
- Tenant switcher sets active tenant cookie; BFF forwards `X-Tenant-Id`.
- Role guards on settings/admin routes.

### 10.5 State management rules

- No global store for server entities; Query keys: `['task', id]`, `['repo', id]`, …
- SSE updates patch Query cache by sequence number.
- Optimistic UI only for reactions/comments; never approvals.
- Diffs virtualized; do not keep full file trees in memory.

### 10.6 Frontend modules (folders)

`apps/web/src/app/**` routes · `features/tasks|repos|chat|settings|analytics|auth` · `shared/ui` · `shared/api` · `shared/auth` · `shared/streaming`

---

## 11. Infrastructure LLD

### 11.1 Docker

| Image | Contents | Notes |
|---|---|---|
| `alama-api-gateway` | Gateway | Distroless, non-root |
| `alama-bff-web` | BFF | |
| `alama-svc-*` | Each Python service | Multi-stage |
| `alama-worker-agent` | Temporal worker | |
| `alama-worker-index` | Indexing | May need parser deps |
| `alama-sandbox` | Hardened tool image | Separate signing policy |
| `alama-web` | Next.js | |

Every image: pinned base digest, SBOM, signature, HEALTHCHECK.

### 11.2 Docker Compose (local/dev)

Services: Postgres (multiple DBs), Redis, Kafka (or Redpanda), OpenSearch, Temporal, MinIO, mailhog, all app services.  
**Not for prod.** Compose profiles: `core`, `ai`, `full`.

### 11.3 Kubernetes

| Object | Purpose |
|---|---|
| Namespaces | `alama-cell-{id}`, `alama-system`, `alama-sandbox` |
| Deployments/Rollouts | Services + workers |
| StatefulSets / operators | Only if self-hosting (prefer managed data) |
| Services | ClusterIP internal; NodePort forbidden |
| Ingress / Gateway API | External HTTPS, WAF, TLS | 
| HPA | API/BFF CPU+RPS |
| KEDA | Queue depth for workers |
| PDB | minAvailable for gateway/workflow |
| NetworkPolicy | Default deny; allow explicit |
| ResourceQuota / LimitRange | Per namespace |
| PriorityClass | `critical` (gateway, temporal), `batch-index` |
| ServiceAccount + Workload Identity | Cloud access |
| ConfigMap | Non-secret config |
| Secret / ExternalSecrets | Secrets from manager |
| Horizontal scaling | Add pods; cell scale-out for tenants |

### 11.4 Autoscaling signals

| Workload | Signal |
|---|---|
| api-gateway / bff | RPS, p95 latency, CPU |
| task-service | RPS + DB pool wait |
| agent-worker | Temporal schedule-to-start latency |
| indexing-worker | Kafka lag / queue age |
| model-gateway | Concurrency saturation |

### 11.5 CI/CD

Pipeline stages: lint → typecheck → unit → contract → security scan → build/sign image → integration → deploy ephemeral → e2e → promote staging → canary cell → prod cells.  
GitOps (Argo/Flux-class) for K8s manifests. DB migrations job before app rollout (expand-first).

---

## 12. Observability LLD

### 12.1 OpenTelemetry

- Propagate W3C `traceparent` across gateway → services → Temporal → activities → Model/Tool.
- Attributes: `tenant_id_hash`, `task_id`, `repository_id`, `workflow_id`, `model_name`, `tool_name`, `index_generation_id`, `cell_id`.
- Never put prompts/source in span attributes by default.

### 12.2 Metrics (Prometheus)

Golden + product:

- `http_request_duration_seconds`
- `task_state_transitions_total`
- `task_success_rate` / `task_fail_rate`
- `index_lag_seconds`
- `retrieval_latency_seconds` / `retrieval_empty_total`
- `model_tokens_total` / `model_cost_usd_micros_total`
- `tool_invocations_total` / `tool_failures_total`
- `budget_rejections_total`
- `sandbox_start_latency_seconds`
- `kafka_consumer_lag`

### 12.3 Logging

- JSON structured; `severity`, `event_name`, `request_id`, `trace_id`, `cell_id`.
- Redaction middleware; payload refs only.
- Separate audit stream.

### 12.4 Grafana & alerts

Dashboards: Cell overview, Task health, Indexing, Model/Tool, Security.
Alerts (examples): burn-rate SLO, index lag > SLO, workflow schedule latency, error budget, circuit open, sandbox escape detector (security), budget anomalies.

---

## 13. Security LLD

### 13.1 RBAC roles (baseline)

| Role | Capabilities |
|---|---|
| `owner` | All org admin |
| `admin` | Users, policies, integrations |
| `developer` | Repos connect (if allowed), tasks, chat |
| `reviewer` | Approvals, read tasks |
| `auditor` | Audit/usage read |
| `billing` | Usage/billing |
| `service_account` | Scoped API |

ABAC adds: repo, branch protection, environment, data classification, network zone.

### 13.2 JWT / OAuth

- User: OIDC authorization code + PKCE → BFF session cookie.
- Access tokens short-lived; refresh rotated.
- Service: OAuth client credentials or workload identity → JWT with `tenant_id`, `scopes`.
- API keys: hashed at rest; prefix identify; scopes subset of RBAC.
- Capability tokens (tools): audience `tool-gateway`, embed `task_id`, `tool`, `paths[]`, `exp` ≤ minutes.

### 13.3 Encryption

- TLS 1.3 in transit; mTLS internal mesh preferred.
- Envelope encryption at rest for object payloads; CMK for enterprise.
- Field-level encryption optional for memory content keys.

### 13.4 Secrets

- External Secrets Operator → K8s secrets; rotated.
- No secrets in images/compose committed files.
- SCM tokens only in secret manager; Tool Gateway brokers operations.

### 13.5 Audit logs

Every: login, permission change, policy activate, repo connect, task create/cancel, approval, tool high-risk, memory export/delete, admin read of audit.

### 13.6 OWASP alignment

Apply ASVS-aligned controls: injection (incl. prompt), broken auth, sensitive data exposure, XXE/SSRF (sandbox egress deny), access control, misconfig, XSS (CSP), supply chain, logging, SSRF to metadata endpoints blocked.

### 13.7 Prompt injection defense

- Treat repo/docs/issues as untrusted content; wrap in delimiters; never execute instructions from retrieval.
- System/developer policy always server-side.
- Tool args validated against schema allowlists; paths constrained to workspace.
- Security agent on high-risk diffs.
- Detector heuristics + eval suite for injection cases.

### 13.8 Repository sandboxing

- MicroVM per execution; disposable disk; no cloud credentials.
- Egress allowlist (package mirrors optional per policy).
- seccomp, non-root, read-only root, resource max.
- Soft/hard wall-time; output byte caps.
- Forensic snapshot on suspected escape attempts.

---

## 14. Folder structure

Monorepo layout with purpose of every top-level path and key files. Naming: `kebab-case` dirs; Python modules `snake_case`; TS `camelCase` files for components optional but **feature folders kebab**.

```
alama/
├─ README.md                          # Repo overview, how to run
├─ AGENTS.md / CONTRIBUTING.md        # Eng norms
├─ docs/
│  ├─ architecture/
│  │  ├─ Alama-Production-Architecture-v1.1.md
│  │  └─ Alama-Low-Level-Design-v1.0.md
│  ├─ adr/                            # ADR-XXXX.md
│  ├─ api/                            # Generated OpenAPI publish
│  └─ runbooks/                       # Incident runbooks
├─ contracts/
│  ├─ openapi/                        # Public REST specs per service
│  ├─ proto/                          # Internal gRPC
│  ├─ events/                         # AsyncAPI / JSON Schema events
│  └─ policy/                         # Policy input/output schemas
├─ apps/
│  ├─ web/                            # Next.js frontend
│  │  ├─ package.json
│  │  ├─ src/app/                     # Routes
│  │  ├─ src/features/                # Feature modules
│  │  └─ src/shared/                  # UI, api client, auth
│  ├─ api-gateway/
│  └─ bff-web/
├─ services/
│  ├─ identity-service/
│  │  ├─ pyproject.toml
│  │  ├─ src/identity_service/
│  │  │  ├─ domain/
│  │  │  ├─ application/
│  │  │  ├─ adapters/
│  │  │  └─ main.py                   # Composition root
│  │  ├─ tests/
│  │  └─ migrations/
│  ├─ repository-service/             # same layout pattern
│  ├─ task-service/
│  ├─ policy-service/
│  ├─ retrieval-service/
│  ├─ knowledge-service/
│  ├─ model-gateway/
│  ├─ tool-gateway/
│  ├─ audit-service/
│  ├─ usage-service/
│  └─ notification-service/
├─ workers/
│  ├─ agent-worker/
│  │  ├─ workflows/                   # Temporal workflows
│  │  ├─ activities/                  # Plan/Execute/Verify/...
│  │  ├─ agents/                      # Role prompts adapters
│  │  └─ protocols/                   # Artifact schemas
│  ├─ indexing-worker/
│  │  ├─ pipeline/
│  │  ├─ parsers/                     # Tree-sitter facades
│  │  ├─ chunking/
│  │  └─ publishers/
│  └─ evaluator-worker/
├─ gateways/                          # Optional shared provider kits (no domain)
├─ packages/
│  ├─ py-alama-common/                # logging, auth principal, errors, otel
│  ├─ py-alama-contracts/             # generated stubs
│  ├─ ts-alama-api-client/
│  └─ ts-alama-ui/                    # design system
├─ platform/
│  ├─ temporal/                       # namespace config notes
│  ├─ schemas/                        # shared enums
│  └─ observability/                  # dashboards as code
├─ infra/
│  ├─ terraform/                      # cells, networks, data stores
│  └─ modules/
├─ deploy/
│  ├─ helm/alama/                     # charts
│  ├─ kustomize/                      # overlays per env/cell
│  ├─ docker/                         # Dockerfiles
│  └─ compose/                        # docker-compose*.yml
├─ security/
│  ├─ threat-models/
│  ├─ policies/                       # OPA/Cedar bundles source
│  └─ prompts-safety/                 # injection corpora
├─ tests/
│  ├─ contract/
│  ├─ integration/
│  ├─ e2e/
│  ├─ load/
│  └─ security/
├─ evals/
│  ├─ agent/
│  ├─ retrieval/
│  ├─ safety/
│  └─ cost/
└─ tools/
   ├─ codegen/
   ├─ lint/
   └─ release/
```

### Per-service mandatory files

| File | Purpose |
|---|---|
| `README.md` | Ownership, SLO, how to run |
| `pyproject.toml` / `package.json` | Deps |
| `src/.../main.py` | DI composition root |
| `migrations/` | DB migrations |
| `tests/unit` `tests/integration` | Tests |
| `deploy/` pointers | Chart values |
| `openapi.yaml` or contracts ref | API |
| `OWNERSHIP` / CODEOWNERS entry | Reviewers |

### Naming conventions

| Kind | Convention |
|---|---|
| Services | `{bounded-context}-service` |
| Workers | `{job}-worker` |
| Python packages | `snake_case` |
| TS components | `PascalCase.tsx` |
| DB tables | `snake_case` plural |
| Events | `com.alama.{context}.{entity}.{action}.v1` |
| Metrics | `alama_{subsystem}_{metric}_{unit}` |
| Prompt templates | `{role}.{purpose}.v{n}` |

---

## 15. Testing strategy

| Layer | Scope | Owner | Gate |
|---|---|---|---|
| Unit | Domain/application pure logic | Service team | PR |
| Contract | OpenAPI/proto/event schemas consumer/provider | Platform | PR |
| Integration | DB, Kafka, Redis, Temporal test env | Service team | PR |
| E2E | Login→connect→task→PR happy path | QA/platform | Merge/staging |
| Load | Task create RPS, index lag, retrieve p95 | Platform | Pre-prod |
| AI Evaluation | Agent success, retrieval recall@k, citation attribution, safety | Agent team | Canary promote |
| Security | SAST/DAST, dep scan, sandbox escape suite, prompt injection corpus | Security | Release |

**AI eval harness:** golden repos; deterministic graders + LLM-as-judge with rubric; cost/quality Pareto; block release on regression beyond threshold.

---

## 16. Coding standards

### 16.1 Python

- 3.12+; type hints mandatory on public functions; `ruff` + `mypy` strict for domain/application.
- One obvious package layout: domain / application / adapters.
- No bare `except:`; use typed errors from §3.2.
- Async for I/O services; sync allowed in CPU parse workers with clear process pool.
- Pydantic models at boundaries only; domain entities remain pure dataclasses/attrs without framework.

### 16.2 TypeScript / React

- `strict` TypeScript; no `any` without eslint waiver + reason.
- Server Components by default; client only for interactivity.
- Accessible components (ARIA); no business logic in UI components — hooks/features layer.
- API types generated from contracts; forbid hand-copied DTOs.

### 16.3 Naming

- Prefer domain language from bounded contexts (`Task`, not `Job` unless queue job).
- Boolean names: `is_`, `has_`, `can_`.
- Avoid abbreviations except universal (`id`, `url`, `sha`).

### 16.4 Architecture rules (enforced in CI)

1. Dependency direction: adapters → application → domain (only inward).
2. No cross-service DB reads.
3. No provider SDK outside `model-gateway` / SCM adapters.
4. No secrets in logs.
5. Every new endpoint has OpenAPI + contract test + authz annotation.
6. Every Temporal activity declares idempotency and retry policy.
7. Feature flags expire ≤ 90 days or tracked exception.

### 16.5 SOLID / Clean Architecture / DDD

- **S:** One reason to change per module (e.g., `HybridRetriever` ≠ embedding provider).
- **O:** New SCM provider = new adapter, not rewrite of repository-service core.
- **L:** Provider adapters substitutable behind ports.
- **I:** Narrow ports (`Embedder` ≠ full `ModelGateway` if only embed needed in indexing).
- **D:** Domain depends on abstractions.
- **DDD:** Aggregates enforce invariants (`Task` state machine); domain events via outbox.
- **Clean Architecture:** composition root only place that knows concrete classes.

---

## 17. Implementation readiness checklist

Before coding a vertical slice (repo connect → index → task → PR):

- [ ] HLD ADRs accepted; this LLD reviewed by service owners
- [ ] OpenAPI + event schemas drafted for the slice
- [ ] Tables/migrations designed for identity/repository/task/index_meta
- [ ] Temporal workflow state machine diagram approved
- [ ] Tool catalog + policy inputs defined
- [ ] Prompt templates v1 checked into registry format (not hardcoded)
- [ ] Threat model updated for sandbox + injection
- [ ] SLO dashboards & alerts stubs created
- [ ] Eval golden set (even small) exists
- [ ] Local compose profile boots dependencies
- [ ] Security review of capability token design signed off

### Recommended first vertical slice modules

1. `identity-service` (minimal tenant/subject)
2. `repository-service` + GitHub adapter + webhook
3. `indexing-worker` (single language) + `retrieval-service`
4. `task-service` + `agent-worker` (Planner+Coder+Tester only)
5. `model-gateway` + `tool-gateway` + sandbox
6. `apps/web` dashboard + task + chat
7. Then Reviewer/Security/Memory/Policy hardening

---

## Appendix A — Artifact schema index (names only)

`Plan`, `PlanStep`, `RetrievalPack`, `EvidenceItem`, `Citation`, `ToolCallIntent`, `ToolResult`, `ToolReceipt`, `DiffBundle`, `TestReport`, `ReviewReport`, `SecurityReport`, `Reflection`, `RecoveryAction`, `MemoryCandidate`, `UserSummary`, `PolicyDecision`, `CapabilityToken`, `IndexGenerationStats`

## Appendix B — Status code usage cheat sheet

| Code | When |
|---|---|
| 200 | Sync read/update success |
| 201 | Resource created |
| 202 | Accepted async (reindex, long task) |
| 204 | Deleted / no body |
| 400 | Malformed |
| 401 | Unauthenticated |
| 403 | Unauthorized / policy deny |
| 404 | Not found in tenant |
| 409 | State conflict |
| 412 | Precondition (stale index) |
| 422 | Semantic validation |
| 429 | Rate limit / budget |
| 500 | Unexpected |
| 502 | Bad dependency fatal |
| 503 | Transient dependency |

---

*End of Low-Level Design v1.0 · Bound to Architecture v1.1 · No source code included*
