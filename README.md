# Platt

Platt is an embodied DevOps agent for Azure DevOps and Azure. This repository delivers the Phase 1 event slice: a FastAPI streaming backend and a React/Vite browser shell with an animated low-poly 2D office stage.

## Repository Map

```text
backend/     FastAPI app, event contract, websocket, persisted streaming chat job
frontend/    React + Vite shell, animated 2D office stage, audit and chat UI
artefacts/   PRD and planning reports
docs/        development, CI, repository governance
```

## Local Development

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest
.venv/bin/uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## Current Scope

Implemented:

- Typed Phase 1 backend event contract for PRD section 7.3.
- `/health`, `/ws`, and `/chat`; chat uses a swappable Anthropic streaming client and publishes typed state and delta events.
- Local-only repository onboarding via `POST /onboarding`: inventories bounded files,
  Terraform module sources, a local Terraform module graph (variables, outputs, and
  safe relative-source edges), and Azure Pipeline YAML path filters, then persists the
  result in SQLite. It never clones repositories or contacts Azure, Terraform, or git remotes.
- Audited read-only repository tools for an onboarding record: bounded file reads,
  inventory globbing, and literal content search. Every invocation revalidates the
  trusted checkout and rejects paths outside the recorded inventory.
- A repeatable ten-question acceptance suite over `seed-infra`, covering module
  traces, pipeline discovery, provider posture, resource definitions, and
  governance conventions through the onboarding APIs.
- A local repository onboarding panel that displays bounded inventory and graph
  facts, prepares an explicit read-only review-plan preview, then scopes
  subsequent chat requests to that onboarding record. Preparing the preview
  records an audit event but does not run its listed tools.
- React/Vite shell with the audit inspector, chat panel, animated office, speech bubble, and state-specific Platt rig.
- Orca work packages for planning, backend, frontend, and operations.

Not implemented yet:

- Azure DevOps integration, Terraform tools, Azure MCP integration, real 3D assets, private GitHub publish, and a production API host.

Set `ANTHROPIC_API_KEY` to enable live streaming replies. Without it, Platt streams a safe configuration message and returns to idle; `/dev/state-cycle` remains available to exercise every visual state without credentials.

## Local onboarding API

Configure `PLATT_ONBOARDING_ROOT` to the app-owned directory containing checked-out
repositories, then provide the absolute path of a repository beneath that root:

```bash
curl -X POST http://127.0.0.1:8000/onboarding \
  -H 'content-type: application/json' \
  -d '{"repository_path":"/absolute/path/to/repository"}'
```

Retrieve the persisted response with `GET /onboarding/{id}`. Use
`GET /onboarding/{id}/module-trace?module_path=modules/example` to obtain a
deterministic local-module path back to the repository root. Only relative sources
that resolve to a directory inside the checked-out repository become graph edges.

`GET /onboarding/{id}/tools` advertises three read-only repository tools. Call
`POST /onboarding/{id}/tools/invoke` with a tool name and its one argument:

```bash
curl -X POST http://127.0.0.1:8000/onboarding/{id}/tools/invoke \
  -H 'content-type: application/json' \
  -d '{"tool":"grep","arguments":{"query":"azurerm_storage_account"}}'
```

The tools are `read_file` (`path`), `glob` (`pattern`), and literal `grep`
(`query`). They only read paths from the original bounded inventory, revalidate
the trusted checkout before every call, reject symlinks, record an audit entry,
and report when their 500-path or one-megabyte search budgets truncate results.

Use `POST /onboarding/{id}/chat` with the normal `{"prompt":"..."}` body to
start a chat job with a metadata-only summary of that onboarding record. The
summary treats repository content as untrusted data, lists detected modules and
pipeline files, and never represents a repository tool as having run.

Records are stored in the owner-only `.platt/` app-state directory by default; set
`PLATT_ONBOARDING_DB` to use another local SQLite path. Scanning is capped at 5,000
files and 2,000 directories, does not follow symlinks, and skips common
generated/metadata directories.

## Publishing Blockers

`gh` is installed, but the configured GitHub token is invalid. Re-authenticate with `gh auth login -h github.com` before creating the private repo, pushing, opening PRs, or connecting Vercel to GitHub.
