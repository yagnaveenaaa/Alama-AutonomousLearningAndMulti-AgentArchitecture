# Alama Web (`apps/web`)

Next.js App Router frontend for the first vertical slice (LLD §10): **dashboard**,
**tasks**, and **chat**.

## Routes

| Route | Purpose |
|---|---|
| `/login` | SSO entry (local session cookie stand-in for OIDC PKCE) |
| `/` | Dashboard — `TaskList`, `RepoStatus`, `UsageWidget` |
| `/tasks` | Task list |
| `/tasks/[taskId]` | Timeline + approval banner |
| `/chat` | Composer → create task |

## Layout

```
src/app/**                 routes
src/features/tasks|repos|chat|analytics|auth
src/shared/ui|api|auth|streaming
```

## Run

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000 — middleware redirects to `/login` until the session cookie is set.

```bash
npm run typecheck
npm test
npm run build
```

## Data

By default `shared/api/client.ts` uses an in-browser mock.

For the **live vertical slice**, set:

```bash
# PowerShell
$env:NEXT_PUBLIC_BFF_URL="http://127.0.0.1:8081"
```

and start BFF with `BFF_ENABLE_VERTICAL_SLICE=true` (see `compose/run-vertical-slice.ps1`).

## Docker

```bash
cd apps/web
docker compose up --build
```

Serves on host port **3000**.
