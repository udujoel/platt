# Platt

Platt is an embodied DevOps agent for Azure DevOps and Azure. This repository starts with the Phase 1 skeleton from the PRD: a FastAPI event backend and a React/Vite browser shell with a placeholder 3D stage.

## Repository Map

```text
backend/     FastAPI app, event contract, websocket, fake chat job
frontend/    React + Vite shell, R3F placeholder stage, chat/status UI
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
- `/health`, `/ws`, and `/chat` placeholder job streaming fake events.
- Local-only repository onboarding via `POST /onboarding`: inventories bounded files,
  Terraform module sources, and Azure Pipeline YAML path filters, then persists the
  result in SQLite. It never clones repositories or contacts Azure, Terraform, or git remotes.
- React/Vite shell with full-bleed stage, chat panel, status chip, and fake event cycle.
- Orca work packages for planning, backend, frontend, and operations.

Not implemented yet:

- Anthropic streaming, Azure DevOps integration, Terraform tools, Azure MCP integration, real 3D assets, private GitHub publish, and Vercel deployment.

## Local onboarding API

Provide the absolute path of a repository that already exists on the backend host:

```bash
curl -X POST http://127.0.0.1:8000/onboarding \
  -H 'content-type: application/json' \
  -d '{"repository_path":"/absolute/path/to/repository"}'
```

Retrieve the persisted response with `GET /onboarding/{id}`. Records are stored in
SQLite at `/tmp/platt-onboarding.sqlite3` by default; set `PLATT_ONBOARDING_DB` to use
another local SQLite path. Scanning is capped at 5,000 files and 2,000 directories,
does not follow symlinks, and skips common generated/metadata directories.

## Publishing Blockers

`gh` is installed, but the configured GitHub token is invalid. Re-authenticate with `gh auth login -h github.com` before creating the private repo, pushing, opening PRs, or connecting Vercel to GitHub.
