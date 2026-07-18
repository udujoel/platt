# Platt Roadmap

## Product promise

Platt is an embodied, auditable agent for Azure DevOps and Azure. Its character
is a truthful projection of work in progress: the user should be able to see
what Platt is doing, inspect the underlying job history, and understand when a
real system needs their decision.

## Current product boundary

Version `0.1.0` is a locally validated Phase 1 slice. It has a typed streaming
event contract, persisted audit/job records, a bounded local repository
onboarding flow, and a React/Vite interface with an animated 2D office stage.
The 2D stage remains the supported v0.x embodiment.

**A 3D React Three Fiber (R3F) character is mandatory for the next major
release.** It is not optional polish and must keep the existing event-state
contract, provide a reduced-motion/accessibility fallback, and be verified in
the deployed product. No v0.x work may represent the current CSS stage as a
completed 3D implementation.

## Delivery sequence

### 0.1.1 — Reliability and release discipline (current checkpoint)

- Handle a WebSocket send that races a closed transport without emitting an
  unhandled ASGI error; retain regression coverage.
- Make backend tests, frontend production builds, and Terraform formatting
  mandatory GitHub CI gates.
- Establish the changelog, version history, roadmap, and human-readable
  development log.
- Verify the checkpoint locally, on its PR, and through a Vercel preview.

### 0.2 — Bounded repository intelligence and safe tool control

- Build on the existing local-only onboarding inventory; do not reimplement it.
- Started with a frontend local-repository onboarding panel: it shows bounded
  inventory/graph facts, prepares a read-only review-plan preview, and sends
  subsequent questions through the scoped onboarding-chat endpoint.
- Started turning discovered repository facts into inspectable, bounded job
  plans with explicit tool inputs, outputs, and audit records. Plan creation
  cannot execute repository tools.
- Add tests for path boundaries, refusal behavior, retries, reconnects, and
  event ordering before enabling any remote side effect.

### 0.3 — Deployable service boundary

- Select and verify a production backend host before claiming a production
  Platt experience. Vercel currently hosts only the static frontend.
- Configure explicit preview/production API origins and WebSocket CORS,
  health checks, deployments, and rollback evidence.
- Do not add a paid service, secret, or ownership/access change without user
  direction.

### 0.4 — Azure DevOps and Azure execution with a structural approval gate

- Replace seed placeholders with validated, least-privilege Azure DevOps and
  Azure integrations.
- Require an inspectable plan and a structural approval boundary before any
  mutation, including Terraform apply or pipeline changes.
- Never infer approval from chat text alone; persist the request, approver,
  scope, and outcome in the audit trail.

### 1.0 — 3D embodied Platt

- Ship the mandatory R3F character and state rig, driven by the same truthful
  job/event state as the 2D implementation.
- Preserve keyboard operation, readable status/audit views, reduced-motion
  behaviour, responsive performance, and a tested non-WebGL fallback.
- Version, document, deploy, and verify this as the next major release only
  when the 3D representation is genuinely present and usable.

## Verified risks to reduce

- The Vercel frontend has no verified production backend endpoint, and the
  backend's present origin policy only accepts local Vite development origins.
- SQLite persistence and the in-process event bus are appropriate for a local
  slice, not multi-instance/reconnect-resilient production delivery.
- Azure seed infrastructure still contains placeholder identifiers and has not
  been applied against an Azure subscription or Azure DevOps organization.
- Configuration naming has drifted: documentation mentions
  `PLATT_DATABASE_URL`, while the current persistence code reads
  `PLATT_DB_PATH`.
- Automated PR reviewers can be quota- or rate-limited. Reviews must be
  checked after the required waiting period, but no paid bypass is permitted.

## Checkpoint rule

Every completed checkpoint updates this roadmap, `CHANGELOG.md`,
`docs/devlog.md`, and `docs/versioning.md`. It is accepted only after the
relevant automated checks, live verification, deployment evidence, and PR
review handling are recorded.
