# Changelog

All notable product and delivery changes are recorded here. Platt follows
[Semantic Versioning](https://semver.org/) while it is pre-1.0: new bounded
capabilities use a minor version and backwards-compatible corrections use a
patch version.

## Unreleased

### Added

- A frontend local-repository onboarding workflow that surfaces bounded file,
  Terraform graph, and pipeline counts, then scopes chat to the resulting
  onboarding record.
- An audited read-only repository review-plan preview that shows bounded tool
  inputs and expected outputs without executing a tool.
- A bounded recent-event replay endpoint and reconnecting local client that
  recover persisted event history in stable order without duplicate rendering.
- Explicit per-step execution for pre-planned read-only repository work, with
  bounded results and audit events linked to the original plan job.
- Automated frontend retry-policy coverage, including exponential backoff,
  capped delays, and stable-connection resets, enforced in CI.
- A validated `PLATT_ALLOWED_ORIGIN_REGEX` backend setting for explicit API
  origins, while retaining the safe local-Vite-only default.
- Browser WebSockets now enforce that same approved-origin policy before a
  connection is accepted.

## [0.1.1] — 2026-07-18

### Added

- GitHub Actions quality gates for backend tests, frontend builds, and
  Terraform formatting.
- A maintained roadmap, development log, and versioning policy.

### Fixed

- WebSocket delivery now treats a send that races a closed client transport as
  a normal disconnect rather than an unhandled server error.

## [0.1.0] — 2026-07-18

Initial versioned Phase 1 baseline:

- FastAPI event contract, health endpoint, persisted audit records, local-only
  repository onboarding, and streamed chat jobs.
- React/Vite audit inspector, chat panel, and accessible animated 2D office
  stage that maps agent state to a visible Platt character.
- Azure seed-infrastructure scaffold and local onboarding guidance.

This baseline has package versions but no historical Git tag. Future released
versions must be tagged from a verified merge commit.
