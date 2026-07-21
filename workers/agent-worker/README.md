# agent-worker

Temporal-class agent control loop hosting Planner → Coder → Verifier
(Tester + Reviewer + Security) (LLD §2.15 / §6). Queue: `agent-general`.

## Responsibility

| Component | Role |
|---|---|
| `AgentWorkflow` | Durable Planner→Executor→Verifier loop |
| `PlanActivity` | ContextBuilder + Planner → `Plan` |
| `ExecuteStepActivity` | Coder → tool intents → Tool Gateway → `DiffBundle`/`StepResult` |
| `VerifyActivity` | Tester + Reviewer + Security → reports + deterministic gate |
| `AgentMessageBus` | Typed artifact handoffs (no free chat) |
| `ContextBuilder` | Working memory + retrieval pack |

Side effects only via **Model Gateway** and **Tool Gateway** ports.

## Hardening scope (this module)

- Roles enabled: **Planner**, **Coder**, **Tester**, **Reviewer**, **Security**
- Step tags `test` / `review` / `security` select which checks run; high-risk steps always get Security
- Security includes deterministic secret scan + model `security.vN` template
- Reviewer uses `reviewer.vN` vs objective/policy
- Recovery / Memory Writer / Documentation still deferred
- `LocalWorkflowRuntime` stands in for Temporal locally

## Run

```bash
pip install -e packages/py-alama-common
pip install -e workers/agent-worker[dev]
agent-worker
```

Enqueue work programmatically via `enqueue(container, AgentWorkflowInput(...))`.

## Docker

```bash
cd workers/agent-worker
docker compose up --build
```

## OpenAPI

Not applicable — this is a Temporal/worker deployable, not an HTTP API.
