# api-gateway

Stateless edge gateway: JWT/session authn, tenant→cell routing, hierarchical
rate limits, body size limits, reverse proxy to cell services (LLD §2.1 / §13.2).
Port **8080**. No database.

## Responsibility

| Module | Role |
|---|---|
| `authn` | `TokenValidator` — HS256 JWT (local) / session cookie bridge |
| `routing` | `TenantRouter` — tenant cell + path → upstream service |
| `ratelimit` | IP / subject / tenant fixed-window counters |
| `proxy` | Forward with `X-Subject-Id`, `X-Tenant-Id`, `X-Request-Id` |
| `GatewayMiddleware` | auth → route → limit → proxy |

**Not proxied publicly:** model-gateway, tool-gateway (internal only).

## Routes

| Path | Behavior |
|---|---|
| `GET /health` | Liveness |
| `GET /ready` | Readiness + upstream mode |
| `POST /v1/gateway/dev/mint-token` | Local token mint (dev) |
| `/v1/**` | Authenticated reverse proxy |

## Local run

```bash
pip install -e packages/py-alama-common[fastapi]
pip install -e services/api-gateway[dev]
api-gateway
```

Default `GATEWAY_USE_ECHO_UPSTREAM=true` echoes proxied calls (no backends required).

## Docker

```bash
cd services/api-gateway
docker compose up --build
```

## Notes

- Production swaps `LocalJwtTokenValidator` for OIDC JWKS validation.
- WAF sits in front of ingress; gateway enforces body size + coarse quotas only.
