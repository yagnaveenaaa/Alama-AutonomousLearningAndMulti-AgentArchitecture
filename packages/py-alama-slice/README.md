# py-alama-slice

Local **vertical slice** for Alama:

`objective → import fixture repo → index → plan → retrieve → edit → pytest → approval → local PR`

## Run (CLI)

From monorepo root (after installing deps):

```bash
pip install -e packages/py-alama-common
pip install -e workers/indexing-worker
pip install -e workers/agent-worker
pip install -e packages/py-alama-slice[dev]

alama-slice run --objective "Fix authentication bug"
# approve when prompted, or:
alama-slice run --objective "Fix authentication bug" --auto-approve
```

## What it does

1. Copies `fixtures/auth-bug-repo` into a temp workspace
2. Indexes Python sources via `indexing-worker`
3. Retrieves auth-related evidence
4. Planner/coder (deterministic slice model) patches `src/auth.py`
5. Runs real `pytest` in the workspace
6. Requests approval for opening a PR
7. Writes `.alama/PR.md` + `.alama/change.patch` (local PR artifact)

Limited to the fixture Python repo and one deterministic “model” — enough for a working demo.
