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

`shared/api/client.ts` is a BFF-shaped mock for local UI development. Production
wires TanStack Query keys to `bff-web` GraphQL + REST/SSE streams.

## Docker

```bash
cd apps/web
docker compose up --build
```

Serves on host port **3000**.
