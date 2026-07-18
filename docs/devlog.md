# Platt Development Log

This is the concise, human-readable record of validated delivery decisions.
Detailed implementation and release notes belong in the PR and changelog.

## 2026-07-18 — 0.2.0 release candidate

- Aligned the backend and frontend package declarations, changelog, roadmap,
  and release policy on the bounded repository-intelligence checkpoint.
- The release remains subject to the normal PR checks, CodeRabbit approval,
  deployment verification, and a tag from the verified merge commit.

## 2026-07-18 — Repository-bound plan execution

- Repository-review jobs now persist the onboarding record that created them,
  including a lightweight migration for existing local SQLite job tables.
- Step execution rejects a plan job when its recorded checkout does not match
  the request, preventing a plan prepared for one local repository from being
  reused against another.

## 2026-07-18 — Persisted read-only execution receipts

- Completed repository-review plan steps now emit a bounded receipt into the
  original plan job's persisted event history. File receipts record a path and
  returned byte count; glob and grep receipts record result counts, scan scope,
  and truncation when applicable.
- The receipt is deliberately content-free, preserving the ability to audit an
  explicit local read after the UI result disappears without copying untrusted
  repository text or broadening repository-tool authority.

## 2026-07-18 — Visible backend readiness

- The connected frontend now polls `/ready` on load and every 30 seconds, then
  displays backend readiness independently from its WebSocket connection state.
- An unreadable or malformed readiness response is shown as unavailable rather
  than being mistaken for a healthy backend.

## 2026-07-18 — Persistence-aware readiness probe

- Added a provider-neutral `/ready` endpoint that checks the active SQLite
  connection with a read-only query and returns a generic `503` if it fails.
- This adds a meaningful host integration point without selecting a host or
  exposing database paths or low-level storage errors.

## 2026-07-18 — Hosted frontend configuration guard

- Added a frontend guard that retains local defaults for development but blocks
  a hosted static build without both configured backend URLs before it opens a
  socket or makes an API request.
- The guard makes the unselected production backend boundary visible without
  adding a service, credential, or ownership change.

## 2026-07-18 — Browser WebSocket origin enforcement

- Applied the validated API-origin pattern to WebSocket handshakes before they
  can subscribe or receive an event. The default remains local Vite only; a
  configured preview or production frontend must send a matching `Origin` header.
- This closes the local cross-origin gap without selecting a backend host or
  broadening the existing origin default.

## 2026-07-18 — Configurable API-origin preparation

- Added a validated `PLATT_ALLOWED_ORIGIN_REGEX` setting for explicit backend
  API origins while preserving the existing local-Vite-only default.
- This prepares a future preview or production service boundary without
  selecting a backend host, adding credentials, or claiming WebSocket origin
  enforcement before it exists.

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
