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
- React/Vite shell with full-bleed stage, chat panel, status chip, and fake event cycle.
- Orca work packages for planning, backend, frontend, and operations.

Not implemented yet:

- Anthropic streaming, Azure DevOps integration, Terraform tools, Azure MCP integration, persistence, real 3D assets, private GitHub publish, and Vercel deployment.

## Publishing Blockers

`gh` is installed, but the configured GitHub token is invalid. Re-authenticate with `gh auth login -h github.com` before creating the private repo, pushing, opening PRs, or connecting Vercel to GitHub.

