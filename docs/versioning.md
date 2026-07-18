# Platt Versioning and Release Policy

## Source of truth

The current delivery version is `0.2.0`, declared in
`backend/pyproject.toml` and `frontend/package.json`. A release must update
both declarations, `CHANGELOG.md`, this policy when needed, the roadmap, and
the development log. A verified release merge is tagged `vMAJOR.MINOR.PATCH`.
The `0.1.0` Phase 1 baseline predates this release policy and has no Git tag.

## Pre-1.0 policy

- Patch (`0.1.x`): backwards-compatible reliability, security, documentation,
  and delivery-system improvements.
- Minor (`0.x.0`): a new bounded, user-visible capability or an approved
  expansion of the product surface.
- Major (`1.0.0`): the mandatory R3F 3D character release. It must preserve
  the truthful event mapping and include accessibility and fallback evidence.

The `0.2.0` delivery version was tagged as `v0.2.0` from verified merge
`46b447c`. The in-progress R3F foundation remains unreleased and does not
itself constitute the required 1.0 acceptance evidence.

## Required release evidence

1. Intentional diff review and a clean, scoped branch.
2. Backend tests, frontend production build, Terraform formatting, and any
   new focused regression tests pass.
3. CI succeeds on the PR; a Vercel preview is inspected for relevant UI
   changes. Production is promoted only when its complete user flow is
   verifiable.
4. CodeRabbit and Codex review are checked no earlier than three minutes after
   PR creation and repeatedly thereafter. Valid findings are fixed; rejected
   findings are documented with evidence. Quota/rate limits are recorded and
   never bypassed with paid spend.
5. The merge commit, version, deployment result, and quality-gate evidence are
   added to `CHANGELOG.md` and `docs/devlog.md`.

## Stop conditions

The delivery director asks before changing Platt's core aim, crossing an
explicit no-go boundary, spending money, adding a paid service or secret,
changing access or ownership, taking an irreversible action, or shipping a
change that cannot be verified.
