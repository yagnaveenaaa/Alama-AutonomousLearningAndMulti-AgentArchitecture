# tool-gateway

Internal tool broker on port **8108** (LLD §2.10 / §5.7 / §6.5).

Agents never hold SCM or cloud credentials. They only receive short-lived
capability tokens minted for a specific `task_id` + `tool` + `paths[]` + TTL.

## Pipeline

`schema validate → policy evaluate → verify capability → sandbox RPC → bound output → ToolReceipt → audit`

## API (internal)

- `POST /v1/capabilities/mint` — mint capability (`ToolGateway.MintCapability`)
- `POST /v1/invoke` — invoke tool with capability (`ToolGateway.Invoke`)

Headers: `X-Tenant-Id`, `X-Subject-Id`.

## MVP catalog

`get_file`, `search_code`, `apply_patch`, `list_dir`, `run_tests`, `run_command`
(allowlisted), `open_pr`, `read_ci`, `git_checkout` (sandbox only).

Forbidden by default: raw shell, secret read, cloud admin, force-push, prod deploy,
arbitrary network egress.

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/tool-gateway[dev]
tool-gateway
```

## Docker

```bash
cd services/tool-gateway
docker compose up --build
```
