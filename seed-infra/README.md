# Platt seed infrastructure

This is a reference Azure Terraform repository for Platt's sandbox workflow. It is deliberately small, but follows the conventions Platt is expected to learn: a root module, child modules, a locals-based naming scheme, required governance tags, environment-specific inputs, an Azure remote-state placeholder, and separate plan and apply pipelines.

## Safety model

- `rg-platt-sandbox` is created and budgeted by a separate bootstrap process. This configuration treats it as an existing resource group, so its apply identity cannot create or alter resource groups or subscription-level resources.
- The **plan** service connection uses an identity with `Reader` at the subscription and `Storage Blob Data Contributor` only for the state container.
- The **apply** service connection uses an identity with `Contributor` scoped only to `rg-platt-sandbox` plus state-container data access. It is used only by `pipelines/platt-apply.yml`.
- The apply pipeline downloads the exact `plan.tfplan` produced by the plan pipeline; it never runs a new plan. Its deployment job targets the `platt-sandbox-apply` Azure DevOps Environment, where a human approval check must be configured.

## Layout

```text
backend.tf                         Empty AzureRM backend; CI supplies real values.
backend.hcl.example                Non-secret remote-state settings to copy and replace.
environments/dev.tfvars            Dev sandbox values (no credentials).
modules/naming/                    Repository-wide Azure naming convention.
modules/storage-account/           Example sandbox storage account.
modules/log-analytics-workspace/   Example sandbox monitoring resource.
pipelines/platt-plan.yml           PR plan, validation, and artifact publication.
pipelines/platt-apply.yml          Manually started, approval-gated apply of one plan artifact.
```

## Prerequisites and one-time setup

1. Create `rg-platt-sandbox` and put a low-threshold budget alert on it. Do this outside this repository using a tightly controlled bootstrap identity.
2. Create a dedicated state storage account and private `tfstate` container. Grant each pipeline identity only `Storage Blob Data Contributor` at the container/storage scope required for state.
3. Create two Azure Resource Manager service connections named `platt-plan` and `platt-apply`. Do not grant the application host access to `platt-apply`.
4. Create the Azure DevOps Environment named `platt-sandbox-apply`, then configure an **Approvals and checks** manual approval on it. Limit approvers to the people permitted to deploy the sandbox; do not allow the pipeline's service account to self-approve.
5. Create two Azure DevOps pipeline definitions pointing at `pipelines/platt-plan.yml` and `pipelines/platt-apply.yml`. Record the numeric plan definition ID in the apply pipeline variable group.
6. Create a variable group (or protected pipeline variables) with the names below. Store secrets only in Azure DevOps secret variables or service connections, never in this repository.

Required non-secret pipeline variables:

```text
TFSTATE_RESOURCE_GROUP=<state-resource-group>
TFSTATE_STORAGE_ACCOUNT=<state-storage-account>
TFSTATE_CONTAINER=tfstate
PLAN_PIPELINE_DEFINITION_ID=<numeric-plan-definition-id>
```

`TFSTATE_KEY` may be set if state keys are not derived from the environment. No client secret, subscription ID, tenant ID, access key, PAT, or backend access key belongs in `*.tfvars`, `backend.hcl`, YAML, or source control. The Azure CLI tasks obtain short-lived service-connection credentials at runtime.

The existing sandbox resource group's Azure location is the source of truth for every seeded resource. The repository intentionally does not accept a separate location input, which prevents an accidental cross-region deployment.

The reference Log Analytics workspace explicitly permits Azure Monitor's public ingestion and query endpoints because this small sandbox does not provision a private endpoint. A production environment should set both module inputs to `false` only after private-link ingestion and query connectivity is in place.

## Local use

Copy the backend example outside the repository or replace its angle-bracket values in a local untracked file, then run:

```bash
terraform -chdir=. init -backend-config=/secure/path/backend.hcl
terraform -chdir=. fmt -check -recursive
terraform -chdir=. validate
terraform -chdir=. plan -var-file=environments/dev.tfvars
```

The `storage_account_name` in `environments/dev.tfvars` must be globally unique before a real apply. Terraform needs Azure credentials for `init` against remote state and for `plan`; use a least-privilege identity, not an account owner credential.

## Pipeline use

The plan pipeline runs for pull requests to `main` and publishes `plan.tfplan` plus `plan.json` as the `terraform-plan-dev` pipeline artifact. The apply pipeline has no CI or PR trigger. Start it manually or through the backend only after the backend has stored a human approval record, select the exact successful plan run ID, and enter the approval record ID for audit correlation. Azure DevOps then pauses at the `platt-sandbox-apply` environment check before the apply service connection is used.

Protect `main`, require the plan pipeline as a PR policy, and restrict edits to `pipelines/platt-apply.yml`, service connections, variable groups, and environment checks to platform administrators. These controls keep a pull request from replacing the approved artifact or weakening the gate.
