# CI Check Strategy

Initial required checks:

- Backend unit/contract tests with `pytest`.
- Frontend TypeScript and Vite build.
- Secret scan before any external provider credentials are introduced.

Later required checks:

- Prompt-injection fixtures.
- Approval-gate and blast-radius tests.
- Terraform fmt/validate/plan checks for seed infra.

