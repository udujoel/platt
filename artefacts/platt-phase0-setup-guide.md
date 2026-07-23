# Platt Phase-0 Setup Guide — Azure DevOps + Azure

Goal: give Platt real, least-privilege access to an **Azure DevOps** project (repos, PRs, pipelines,
Boards, Wiki) and an **Azure sandbox** subscription (read for queries; apply scoped to one resource
group inside a pipeline). At the end you'll paste a handful of values to me and I wire them into
Vercel — same flow as the Groq/Neon keys.

Everything below is safe, reversible, and near-zero cost. The design keeps the **apply** credential
inside the pipeline only, so the agent can never apply without a human approval.

---

## 0. Prerequisites (one-time, ~5 min)

Install if you don't have them, then sign in:
```bash
# macOS
brew install azure-cli terraform        # az + terraform
az login                                 # opens browser; sign in
az account show                         # confirm the right tenant/subscription
```
You also need an **Azure DevOps organization** (free): https://dev.azure.com → "New organization".

---

## 1. Azure — sandbox subscription, resource group, budget, state (~10 min)

Pick a personal/throwaway subscription. Run these (edit the names/region if you like):

```bash
# --- variables ---
SUB_ID=$(az account show --query id -o tsv)
TENANT_ID=$(az account show --query tenantId -o tsv)
LOCATION=westeurope
RG=rg-platt-sandbox
STORAGE=platttfstate$RANDOM         # must be globally unique, lowercase, <=24 chars

# --- 1a. sandbox resource group (the ONLY thing apply can touch) ---
az group create -n $RG -l $LOCATION

# --- 1b. low budget alert on the RG (safety) ---
# (Portal is easiest: Cost Management > Budgets > Add. Or via REST/az consumption.)
echo "Set a budget alert on $RG in the Portal: Cost Management + Billing > Budgets (e.g. \$10, 80% alert)."

# --- 1c. remote Terraform state storage ---
az storage account create -n $STORAGE -g $RG -l $LOCATION --sku Standard_LRS --min-tls-version TLS1_2
az storage container create --account-name $STORAGE -n tfstate --auth-mode login

echo "SUB_ID=$SUB_ID  TENANT_ID=$TENANT_ID  RG=$RG  STORAGE=$STORAGE"
```

### 1d. Two service principals (least privilege)

```bash
# SP "plan": Reader on the subscription + Blob Data Contributor on state. Used for Azure queries + plan.
az ad sp create-for-rbac --name platt-plan --role Reader --scopes /subscriptions/$SUB_ID
# note the appId (client id), password (client secret), tenant from the output
PLAN_APP_ID=<appId-from-output>
az role assignment create --assignee $PLAN_APP_ID \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.Storage/storageAccounts/$STORAGE

# SP "apply": Contributor scoped to the sandbox RG ONLY + state. Lives ONLY in the apply pipeline.
az ad sp create-for-rbac --name platt-apply --role Contributor \
  --scopes /subscriptions/$SUB_ID/resourceGroups/$RG
APPLY_APP_ID=<appId-from-output>
az role assignment create --assignee $APPLY_APP_ID \
  --role "Storage Blob Data Contributor" \
  --scope /subscriptions/$SUB_ID/resourceGroups/$RG/providers/Microsoft.Storage/storageAccounts/$STORAGE
```

**Keep the two `create-for-rbac` outputs** (appId + password + tenant). `platt-plan`'s creds go to the
app host (queries). `platt-apply`'s creds go ONLY into the Azure DevOps apply pipeline (step 2.4).

---

## 2. Azure DevOps — project, repo, PAT, connections, pipelines (~15 min)

### 2.1 Project
- In your org (`https://dev.azure.com/<org>`), create a **project** (e.g. `platt`). Note the process
  template (Agile vs Scrum) — Platt auto-detects it, no action needed.

### 2.2 Seed-infra repo
- This repo already contains a ready seed infra in `seed-infra/`. Push it to a new Azure Repos repo:
```bash
# from the platt repo root, create + push seed-infra as its own AzDO repo (or import it via the UI)
# In AzDO: Repos > new repo "platt-seed-infra", then:
git subtree split --prefix seed-infra -b seed-infra-only     # optional: isolate the folder
# or simply copy seed-infra/* into a fresh clone of the new AzDO repo and push.
```
- Fill in the real values in `seed-infra/backend.tf` / `backend.hcl` (the `$STORAGE`, `$RG`, container
  `tfstate` from step 1) and `environments/dev.tfvars`.

### 2.3 PAT (the app-host credential)
- User settings (top-right) > **Personal access tokens** > New token.
- Scopes: **Code** (Read & write), **Build** (Read & execute), **Work Items** (Read & write),
  **Wiki** (Read & write). Expiry: your call.
- Copy the token — this is `AZDO_PAT`.

### 2.4 Two ARM service connections (for pipelines)
- Project Settings > **Service connections** > New > **Azure Resource Manager** > Service principal (manual):
  - **platt-plan**: tenant + subscription + `platt-plan` appId/secret from step 1d.
  - **platt-apply**: tenant + subscription + `platt-apply` appId/secret from step 1d.
- Name them exactly `platt-plan` and `platt-apply`.

### 2.5 Pipelines
- The definitions live in `seed-infra/pipelines/platt-plan.yml` and `platt-apply.yml`.
- Pipelines > New > Azure Repos Git > your seed repo > existing YAML > pick each file. Create both.
- Note each pipeline's **definition ID** (in the URL / pipeline settings).

### 2.6 Wiki + Boards
- Overview > **Wiki** > create; add a page `Environments/dev` (Platt appends to it after applies).
- **Boards** already exists with the project; Platt creates/moves work items via the PAT.

### 2.7 Service hook (so pipeline results push back — no polling)
- Project Settings > **Service hooks** > New > Web Hooks.
- Trigger: "Build completed" (and "Pull request updated" if you like).
- URL: `https://platt-jade.vercel.app/api/hooks/azdo` *(I'll confirm/enable this endpoint when we wire live).*

---

## 3. What to hand me (I put these in Vercel, encrypted)

Paste these values (like you did Groq/Neon) and I'll set them in Vercel Production env and redeploy:

| Env var | From |
|---|---|
| `AZDO_ORG_URL` | `https://dev.azure.com/<your-org>` |
| `AZDO_PROJECT` | your project name (e.g. `platt`) |
| `AZDO_PAT` | step 2.3 |
| `AZURE_TENANT_ID` | step 1 (`TENANT_ID`) |
| `AZURE_SUBSCRIPTION_ID` | step 1 (`SUB_ID`) |
| `PLAN_CLIENT_ID` | `platt-plan` appId (step 1d) |
| `PLAN_CLIENT_SECRET` | `platt-plan` password (step 1d) |
| `PLATT_PLAN_PIPELINE_ID` | step 2.5 |
| `PLATT_APPLY_PIPELINE_ID` | step 2.5 |
| `AZURE_SANDBOX_RG` | `rg-platt-sandbox` (blast-radius guard) |

**Do NOT send me the `platt-apply` secret** — it belongs only inside the AzDO apply pipeline's
`platt-apply` service connection (step 2.4). The app never holds it; that's the structural gate.

---

## 4. Verify (I run these once the vars are in)
1. `GET /api/onboarding` against your real repo → file tree + module graph + pipeline inventory.
2. A read AzDO tool call (list work items / get a PR) succeeds and is audited.
3. The section-10 scenario: "a storage account for app logs in dev" → work items + branch + PR + plan
   summary + an **Approve** card. One human click → apply runs in the pipeline → resource verified →
   wiki updated → work items closed.

## Cost & safety notes
- All resources are in `rg-platt-sandbox`; the blast-radius guard blocks anything outside it or >3
  destroys. Delete the RG (`az group delete -n rg-platt-sandbox`) anytime to zero out spend.
- `platt-plan` is read-only on the sub; `platt-apply` can only touch the sandbox RG and only from the
  pipeline. No prompt can make the agent apply without your click.
