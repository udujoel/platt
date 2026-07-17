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
  Terraform module sources, and Azure Pipeline YAML path filters, then persists the
  result in SQLite. It never clones repositories or contacts Azure, Terraform, or git remotes.
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

Retrieve the persisted response with `GET /onboarding/{id}`. Records are stored in the
owner-only `.platt/` app-state directory by default; set `PLATT_ONBOARDING_DB` to use
another local SQLite path. Scanning is capped at 5,000 files and 2,000 directories,
does not follow symlinks, and skips common generated/metadata directories.

## Publishing Blockers

`gh` is installed, but the configured GitHub token is invalid. Re-authenticate with `gh auth login -h github.com` before creating the private repo, pushing, opening PRs, or connecting Vercel to GitHub.
