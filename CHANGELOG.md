# Changelog

All notable product and delivery changes are recorded here. Platt follows
[Semantic Versioning](https://semver.org/) while it is pre-1.0: new bounded
capabilities use a minor version and backwards-compatible corrections use a
patch version.

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
