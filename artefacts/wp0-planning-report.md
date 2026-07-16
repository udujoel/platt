# WP0 Planning Report

Source: `artefacts/platt-prd2.md`.

## Work Packages

- WP0 Planning and governance: track the PRD, define sequencing, branch policy, publishing policy, and risks.
- WP1 Backend skeleton: FastAPI, typed events, `/health`, `/ws`, `/chat`, fake streaming job, tests.
- WP2 Frontend skeleton: Vite/React shell, R3F placeholder stage, chat panel, status chip, fake state cycle.
- WP3 Operations: README, env template, development docs, CI strategy, GitHub/Vercel prerequisites.

## Recommended Sequence

1. Land the PRD and Phase 1 skeleton in the monorepo layout.
2. Re-authenticate GitHub CLI, create a private GitHub repository, and push the initial scaffold.
3. Use feature branches and pull requests for all subsequent work.
4. Connect Vercel to the GitHub repository only after frontend build is green.
5. Complete Phase 0 Azure/Azure DevOps setup before write-capable agent work.

## Critical Dependencies

- Phase 0 external resources gate real provisioning.
- The event contract gates frontend/backend parallelism.
- Tool allowlists, audit log, and job caps gate write-capable workflows.
- The approval record and pipeline-only apply identity gate Terraform apply.

## Risks

- The PRD was initially untracked, so worker worktrees could not see it.
- The repo was effectively empty, so generated worker scaffolds needed monorepo correction.
- GitHub publishing is blocked until `gh auth login -h github.com` succeeds.

