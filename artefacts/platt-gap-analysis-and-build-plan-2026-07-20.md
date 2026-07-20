# Platt — Gap Analysis & Build Plan

**Date:** 2026-07-20
**Author:** Orchestrator (Opus 4.8) with Joel Udu
**Supersedes for state-of-play:** `artefacts/project-handoff-2026-07-17.md` (stale — predates 26 commits / PR #27)
**Source of truth for scope:** `artefacts/platt-prd2.md`

---

## 1. True current state (origin/main @ d93a0bb, v0.2.0 + Unreleased)

### Built and verified

- **Backend (FastAPI, local single process)**
  - Typed event contract + one WebSocket bus; pydantic event models.
  - SQLite persistence: jobs, events, audit entries (with `job_id` indexes, lifespan ownership, bounded subscriber queues, drain-on-shutdown).
  - Streaming chat jobs (bare loop), dev state-cycle endpoint, `/health`, `/ready` (SQLite read probe).
  - **Local-only** repository onboarding: file-tree inventory, `python-hcl2` module graph, pipeline YAML inventory; persisted onboarding records.
  - Read-only **review-plan** engine: deterministic glob/grep/read plans, per-step explicit execution, content-free receipts, plan bound to originating onboarding record.
  - Origin policy: `PLATT_ALLOWED_ORIGIN_REGEX`, WebSocket origin enforcement, bounded event replay/reconnect.
  - Routers: `audit, chat, dev, events, health, jobs, onboarding, ws`. Service: `onboarding`. `llm.py` present.
- **Frontend (React/Vite)**
  - Section-6-ish shell, chat panel, audit inspector, onboarding panel, readiness indicator, reconnect-policy module (tested).
  - **2D CSS office stage** = supported embodiment.
  - **Lazy-loaded R3F 3D office** with a *procedural* rig (primitive shapes, not a character), per-state pose contract, WebGL-context-loss fallback to 2D. Default bundle 224 kB / 3D chunk 895 kB.
- **Seed infra:** Terraform modules (naming, log-analytics, storage-account), plan/apply pipelines with human approval gate, dev tfvars — **placeholders, never applied**.
- **CI:** GitHub Actions (backend pytest, frontend build, terraform fmt). **Vercel:** static frontend only.

### Not built (gaps vs PRD)

| PRD | Status |
|---|---|
| Real agentic orchestrator (tool-use loop, streaming, per-job allowlists, caps) | Only bare chat loop + read-only local repo tools |
| Azure DevOps connector (scoped PAT client, clone, Boards, Wiki, PRs, pipelines) | Missing — onboarding is local-disk only |
| F3 chat-to-provision (codegen→PR→plan→approve→apply→verify→self-repair) | Missing |
| F4 version-bump job | Missing |
| F5 Boards write + Kanban panel + in-scene wall board | Missing |
| F6 dashboard (pipeline health, PRs, versions, drift, React Flow graph) | Missing |
| F7 wiki documentation append | Missing |
| F8 voice | Missing |
| Durable approval gate (P0) | Missing |
| Privacy-safe persistence / centralized redaction (P0) | Missing |
| Animated **person** (Mixamo glb + clips + controller) | Only procedural box-rig |
| Backend hosting | Local only |

---

## 2. Locked decisions

1. **Hosting:** Vercel-native on the **Hobby (free) tier**, cheapest-possible. Personal testing use only.
2. **Intelligence:** **Groq** (OpenAI-compatible API, free tier, Llama-class tool-calling model). *Not* Anthropic. The `llm_client` abstraction stays provider-swappable so a stronger model can slot into the hard Terraform-codegen step later.
3. **State:** **Neon Postgres** (free tier, autosuspend) for jobs/events/audit/approvals/onboarding. SQLite retained for local dev.
4. **Realtime:** **SSE** (capped ~25s streams + client auto-reconnect + durable event replay) replaces the persistent WebSocket.
5. **Long jobs:** step-based, **resumable**, persisted to Neon. **No Vercel Queues.** Pipeline status returns via **Azure DevOps service hooks → webhook function** (event-driven, no polling). Version-bump uses the single daily Hobby cron.
6. **E2E scope:** real Azure + Azure DevOps sandbox.
7. **Character:** real Mixamo humanoid + ~10 clips → `platt.glb` → gltfjsx → wired controller.
8. **Fleet:** lean 2–3 Sonnet-5 workers in named Orca panes; Opus 4.8 orchestrates and validates every handoff; Fable 5 for ★ expert gates only.

---

## 3. Target architecture (Vercel free-tier native)

```
Browser (Vite static on Vercel)
  ├─ 3D scene (R3F): platt.glb character + office + controller
  ├─ panels: Chat, Kanban, Dashboard (React Flow + Recharts), Audit, ApprovalCard
  └─ SSE client (capped stream + reconnect + replay)  ──┐
                                                        │
Vercel Python Functions (Fluid Compute, FastAPI)  ◄─────┘
  ├─ REST: onboarding, chat, jobs, approvals, dashboard
  ├─ GET /api/events/stream  (SSE, ~25s cap, reads durable event table)
  ├─ POST /api/hooks/azdo    (service-hook webhook: pipeline/PR status)
  ├─ agent orchestrator (Groq tool-use loop, resumable steps)
  └─ tool layer (repo, azdo REST, terraform-local, azure, hcl, research) — all audited
        │
Neon Postgres (free): jobs, events, audit, approvals, onboarding, work-items cache
Azure DevOps (real): repos, PRs, pipelines, Boards, Wiki   (PAT)
Azure (real, read via SP-plan; apply only inside apply pipeline via SP-apply)
Groq (agent brain)
```

**Resumability contract:** every job is a row + ordered steps in Neon. A function invocation advances the job by N bounded steps, persists progress + emits events, and returns. The job is resumed by (a) the watching client, (b) an incoming AzDO service hook, or (c) the daily janitor cron. No single invocation exceeds the function window.

---

## 4. Free-tier cost rules (enforced in code + review)

- Default agent model = a Groq tool-calling model; cheap/mechanical turns may use a smaller Groq model. Provider + model are env-configurable.
- No always-on connections: SSE capped, then client reconnects; no long-poll loops.
- No Vercel Queues; ≤1 cron (daily). Prefer webhooks over polling everywhere.
- Azure: only `rg-platt-sandbox`, tiny resources (storage account / log-analytics), low budget alert, destroy after each test. Blast-radius check blocks anything outside the sandbox rg.
- Keep the 3D renderer lazy-loaded; do not inflate the default bundle.

---

## 5. Build tracks & phases

Legend: `[B]` backend pane · `[F]` frontend/3D pane · `[O]` ops/infra pane · ★ = Fable gate.

### Phase A — Foundation re-platform (gates B/C; do first) `[B]`+`[O]`
- A1 Persistence: SQLite → Neon Postgres (async driver, models, migrations, repo layer). Keep SQLite for local via a config switch.
- A2 Event delivery: WebSocket → SSE over a durable event table; preserve ordering/replay/reconnect.
- A3 Job model: resumable, step-based execution + caps (40 tool calls / 10 min-equiv / 3 self-repair) enforced in code.
- A4 Vercel deploy: `vercel.ts`, Python Fluid-Compute functions, Neon marketplace link, env wiring, preview green.
- ★ **Fable reviews the re-platform** (event durability, resumability, free-tier compute profile).

### Phase B — Agent core (needs A) `[B]`
- B1 Groq agent orchestrator: OpenAI-compatible client via swappable `llm_client`, streaming, tool-use loop, per-job allowlists, audit, caps.
- B2 Tool framework: registry, JSON schemas, executor, audit persistence (extend existing read tools).
- B3 Azure DevOps connector: scoped PAT client, bounded clone workspace, Boards/Wiki/PR/pipeline REST tools, process-template detection. No credential persistence.
- B4 Onboarding upgrade: real clone + HCL graph + pipeline inventory + Boards/Wiki metadata (extend local-only path).

### Phase C — Provision + guardrails (needs B) `[B]`
- C1 ★ Durable approval gate: immutable approval bound to job + plan-hash + commit; one-time/expiring consumption; apply impossible without an approved artifact.
- C2 Provisioning job (F3): requirement extraction, convention-aware Terraform codegen, PR authoring, plan trigger + service-hook return, plan-JSON parse + summary, blast-radius check, Azure verify, wiki append, work-item completion, self-repair ≤3.
- C3 ★ Privacy/redaction (P0): stop retaining raw prompts/payloads; centralized redaction; retention-safe summaries; secret-recovery tests.
- C4 Version-bump job (F4) + Boards/Kanban (F5) + in-scene wall board sync.

### Phase D — Embodiment + panels (parallel with B/C) `[F]`
- D1 Character asset pipeline: Mixamo character + ~10 clips → Blender consolidation → `platt.glb` → `gltfjsx --transform` → typed `Platt.tsx`. (Some manual/guided steps.)
- D2 Office scene (5.2) + PlattController (5.3): crossfades, idle wander, pebble kick, desk/board anchors, streaming speech bubble, camera rig.
- D3 Panels: Dashboard (React Flow module graph + Recharts sparklines), ApprovalCard, Kanban; keep Chat/Audit.
- D4 Frontend SSE client migration from WebSocket; reduced-motion + non-WebGL fallback preserved.

### Phase E — Hardening (needs all) `[B]`+`[F]`
- Tests: caps, approval gate, blast-radius, secret redaction, prompt-injection (poisoned README ignored).
- Run the section-10 E2E validation scenario twice consecutively; fix flakes.
- Voice (F8) only if everything green.
- ★ **Fable acceptance review** against the section-10 scenario.

---

## 6. Orchestration & validation model

- **Opus 4.8 (this session)** = coordinator: assigns tasks, reviews every worker handoff (diff + tests), integrates, keeps `main` green, updates roadmap/changelog/devlog per the checkpoint rule.
- **Sonnet-5 workers** in named Orca panes (`platt-backend`, `platt-frontend`, `platt-ops` as needed), each in its own worktree, one focused task at a time.
- **Fable 5** invoked only at ★ gates and for any genuine architecture/security judgment call.
- Branch policy: feature branch per task → PR → Opus review → merge to `main`. CI gates must pass. No paid service, secret, or ownership change without Joel's direction.

---

## 7. Phase 0 — what Joel must set up (parallel with building)

Only write-capable/apply and live verification block on these; Phases A, D, and most of B proceed without them.

1. **Groq API key** (free tier) → `GROQ_API_KEY`.
2. **Neon Postgres** via Vercel Marketplace (`vercel integration add neon`) → `DATABASE_URL`.
3. **Vercel** — confirm `joeldus-projects/platt`, allow Python functions; Opus wires `vercel.ts` + env.
4. **Azure** — sandbox subscription; `rg-platt-sandbox` + low budget alert; storage account + `tfstate` container; **SP-plan** (Reader + Blob Data Contributor on state); **SP-apply** (Contributor on `rg-platt-sandbox` only + state).
5. **Azure DevOps** — org + project; push seed-infra repo; 2 ARM service connections (`platt-plan`, `platt-apply`) + pipeline definitions; **service hook** → `/api/hooks/azdo`; init wiki (Environments/dev + one incident page); **PAT** (Code RW, Build RX, Work Items RW, Wiki RW).
6. **Character** — free Mixamo (Adobe) account + Blender installed, or a chosen CC0 humanoid handed to Opus.
7. **Env vars** (Opus templates `.env` + Vercel env): `GROQ_API_KEY, DATABASE_URL, AZDO_ORG_URL, AZDO_PROJECT, AZDO_PAT, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, PLAN_CLIENT_ID, PLAN_CLIENT_SECRET`, pipeline IDs, `PLATT_ALLOWED_ORIGIN_REGEX`.

---

## 8. Risks

| Risk | Mitigation |
|---|---|
| Groq/Llama weaker at multi-tool agentic codegen | Deterministic scaffolding for non-LLM steps; tight tool schemas; swappable `llm_client` to drop in a stronger model for codegen only. |
| Vercel Hobby compute/cron limits | Capped SSE, webhooks over polling, no Queues, resumable steps, ≤1 daily cron. |
| Real Azure spend | Sandbox rg only, low budget alert, blast-radius check, destroy-after-test. |
| 3D asset pipeline overrun | Timebox D1; 2D fallback keeps identical event contract (5.5). |
| WS→SSE regressions | Reuse existing replay/reconnect; contract tests before cutover. |
| Prompt injection via repo/PR/changelog | Treat as untrusted data; per-job tool allowlists; injection test in Phase E. |

---

## 9. Task list (initial dispatch)

See generated tasks. First dispatch (lean fleet):
- **T-A1** `[B]` Neon persistence layer + config switch (SQLite local / Postgres prod).
- **T-D1** `[F]` Mixamo→Blender→`platt.glb`→`Platt.tsx` asset pipeline + controller scaffolding.
- **T-A4** `[O]` Vercel Python-function scaffold + `vercel.ts` + Neon link (after T-A1 lands schema).

Opus validates each; ★ Fable reviews the Phase A re-platform before Phase B opens.
