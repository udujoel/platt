# Platt Development Log

This is the concise, human-readable record of validated delivery decisions.
Detailed implementation and release notes belong in the PR and changelog.

## 2026-07-18 — Client reconnect-policy coverage

- Extracted the local WebSocket retry policy into a small shared module and
  added frontend tests for its exponential backoff, cap, and reset behavior.
- Frontend tests now run as a required CI step, closing the remaining automated
  retry-policy coverage gap in the local 0.2 safety work.

## 2026-07-18 — Explicit planned read-only execution

- An operator can now run an individual proposed review-plan step from the
  onboarding panel. The API recomputes the bounded plan, accepts only a listed
  step belonging to the original plan job, and persists its successful or
  refused outcome in that job's audit trail.
- No plan step runs automatically, accepts arbitrary tool arguments, or changes
  a repository, cloud account, pipeline, or other remote system.

## 2026-07-18 — Ordered event recovery after a local reconnect

- Added a read-only, bounded recent-event replay endpoint and made persistence
  ordering deterministic when timestamps tie. The local WebSocket client now
  uses capped retry backoff, rehydrates the replay window after reconnecting,
  de-duplicates known events, and flushes queued live events afterward.
- Added automated ordering coverage for both replay and selected-job history.
  The reconnect interaction remains local-only and does not add a remote side
  effect.

## 2026-07-18 — Inspectable repository review plans

- Added a deterministic, read-only review-plan endpoint that derives proposed
  `glob`, `grep`, and inventoried-file reads from a persisted onboarding
  record. Creating a plan records a job, audit entry, and plan-ready event;
  it does not invoke a repository tool.
- Exposed that plan in the local onboarding panel so an operator can inspect
  each proposed input and expected output before any tool-execution UI exists.

## 2026-07-18 — Repository context reaches the frontend

- Added a local-only onboarding panel to the React interface. An operator can
  submit a checkout path permitted by the backend, review bounded inventory and
  module-graph facts, and continue through repository-scoped chat.
- Validated the full local user flow against the checked-out repository: 89
  files, four Terraform graph nodes, two pipeline files, and an audited scoped
  chat job were observed in the UI.
- Retained the local-only boundary: the browser does not clone repositories,
  acquire credentials, or contact Azure, Azure DevOps, or Git remotes.

## 2026-07-18 — Technical design direction established

- Validated `main` at `b41ca50` with 34 backend tests passing, a successful
  frontend production build, Terraform formatting, and a live local browser
  exercise of streaming state, audit persistence, and the 2D stage.
- Confirmed the Phase 1 promise: Platt should make agent work visible and
  auditable, rather than presenting an ungrounded character animation.
- Recorded the visual product decision: retain the polished 2D character for
  v0.x; a 3D R3F character is a mandatory requirement of the next major
  release.
- Identified the first reliability defect: a WebSocket `send_json` can raise a
  `RuntimeError` when a client transport closes during a send. The current
  checkpoint adds a regression test and treats that race as a normal
  disconnect.
- Identified release-system gaps: no repository CI workflow or durable
  roadmap/changelog/devlog/version policy existed. This checkpoint establishes
  them before broader capabilities are added.
- Deferred production promotion. The static Vercel frontend is deployable, but
  Platt has no verified production backend endpoint or non-local WebSocket
  origin policy yet.

## 2026-07-16 to 2026-07-18 — Phase 1 baseline delivered

- Established the FastAPI/Vite scaffold and typed streaming event contract.
- Connected the frontend to streamed job state, added SQLite audit persistence
  and bounded local onboarding, then added audit/job inspection and Azure seed
  infrastructure.
- Shipped the current animated 2D office stage on `main` in `b41ca50`.

## Next log entry

Record the frontend-onboarding PR merge commit, Vercel preview result,
CI/check status, automated-review disposition, and any review fixes. Do not
mark the slice shipped without all of those facts.
