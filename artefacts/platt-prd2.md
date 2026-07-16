# Platt: An Embodied DevOps Agent
## Product Requirements and Build Specification

**Version:** 2.0
**Owner:** Joel Udu
**Target stack:** Azure DevOps + Azure, browser frontend, Python backend

---

## 1. What Platt is

Platt is an autonomous DevOps agent with a visible body. He renders as a 3D character in a small office scene in the browser. Behind the character sits a real agent backend that operates on a real Azure DevOps project and a real Azure subscription.

Capabilities:

1. **Codebase intelligence.** Plug Platt into any Azure DevOps repo. He clones it, indexes it, parses all Terraform into a module dependency graph, and can answer any question about the code, the pipelines, or the infrastructure. He can trace any module from leaf to root.
2. **Chat to provision.** Ask for a resource in plain language. Platt writes Terraform that follows the conventions already in the repo, opens a PR, runs plan, waits for one click human approval, applies to the cloud, verifies the resource exists, and documents it.
3. **Autonomous maintenance.** He watches for new provider and module versions, researches releases, and opens version bump PRs with a summary and a recommendation.
4. **Work hygiene.** Before any multi step job he decomposes it into work items on Azure Boards and moves them across the board as he completes them.
5. **Documentation.** He maintains wiki pages for environments and appends entries after changes.
6. **Platform health.** A dashboard shows pipeline health, open PRs, version posture, drift, the module graph, and cloud inventory.
7. **Embodiment.** Every backend state is projected onto the character. Idle means he wanders and kicks a pebble. An LLM call in flight means he paces and thinks. Tool execution means he types at his PC. A response means a speech bubble. The body is a live visualization of real system state, never a scripted loop.

---

## 2. System components

Three kinds of work: things to **build**, things to **connect**, things to **set up** once.

### 2.1 Build (application code)

| Component | Description |
|---|---|
| Frontend app | React + TypeScript + Vite. Hosts the 3D scene, chat, and panels. |
| 3D scene | react-three-fiber scene: office diorama, Platt character, animation controller, chat bubble, camera rig. |
| Character state machine | Client side zustand store mapping backend events to animation states and locomotion. |
| Backend service | Python 3.12 + FastAPI. REST for setup and actions, one WebSocket for all realtime events. |
| Agent orchestrator | Agentic loop on the Anthropic SDK (Claude, tool use, streaming). Job model with steps, caps, and typed events. |
| Tool layer | repo tools, Azure DevOps REST tools, Terraform runner tools, Azure query tools, HCL graph tools, release research tool. Every call audited. |
| Onboarding indexer | Clone, file tree index, python-hcl2 parse into a module graph, pipeline YAML inventory, Boards and Wiki metadata. |
| Provisioning job | The end to end chat to provision flow with the approval gate and self repair loop. |
| Version bump job | Ported from the existing agentic Terraform pipeline project: release detection, significance assessment, bump, plan, PR authoring. |
| Panels | Chat, Kanban, Dashboard, Module graph (React Flow), Audit log. |
| Persistence | SQLite: jobs, events, audit entries, onboarding metadata, approval records. |

### 2.2 Connect (external systems the app talks to)

| System | Used for | Protocol |
|---|---|---|
| Azure DevOps | repos, PRs, pipelines, Boards, Wiki | REST API v7.1 with a PAT, git over HTTPS |
| Azure | resource verification, inventory, health | Microsoft's Azure MCP server as primary, Azure SDK for Python as fallback, read identity only |
| Anthropic API | the agent brain | Anthropic Python SDK, model claude-sonnet-4-6, streaming |
| Terraform Registry / GitHub releases | version bump research | HTTPS |

### 2.3 Set up once (infrastructure and accounts)

| Item | Purpose |
|---|---|
| Azure subscription + rg-platt-sandbox | the only resource group the apply identity can touch, budget alert attached |
| Storage account + tfstate container | Terraform remote state |
| Service principal "plan" | Reader on subscription + Blob Data Contributor on state. Used by plan stages and all Azure queries. |
| Service principal "apply" | Contributor scoped to rg-platt-sandbox only + state access. Lives only in the pipeline, never on the app host. |
| Azure DevOps project | target org. Seed infra repo, two ARM service connections (plan, apply), project wiki, Boards. |
| Seed infra repo | a realistic Terraform codebase for Platt to operate on: root module, 2 or 3 child modules, naming and tagging conventions, remote state config, pipelines folder. |
| Pipelines | platt-plan.yml and platt-apply.yml (or one multi stage pipeline). Definitions live in the seed repo. |
| PAT | scopes: Code read/write, Build read/execute, Work Items read/write, Wiki read/write. |
| Anthropic API key | env var on the app host. |

---

## 3. Environment setup guide (Phase 0 in detail)

Run through this before writing application code.

**Azure**
1. Pick a personal or throwaway subscription. Create rg-platt-sandbox. Add a budget alert with a low threshold.
2. Create the state storage account and a tfstate container.
3. Create SP plan: `az ad sp create-for-rbac`, assign Reader at subscription scope and Storage Blob Data Contributor on the state container.
4. Create SP apply: assign Contributor scoped to rg-platt-sandbox and Storage Blob Data Contributor on the state container. Nothing broader.

**Azure DevOps**
5. Create or reuse an org and project. Note the Boards process template (Agile vs Scrum) because work item type names differ. The app should detect this at onboarding rather than hardcode it.
6. Create the seed infra repo. Give it real conventions: a locals based naming scheme, mandatory tags, a modules directory, remote state backend config, an environments/dev tfvars.
7. Create two ARM service connections, one per service principal. Name them platt-plan and platt-apply.
8. Add platt-plan.yml and platt-apply.yml to the repo (spec in section 7.5). Create the two pipeline definitions pointing at them.
9. Initialize the project wiki. Seed a page Environments/dev and one example incident page.
10. Create the PAT with the scopes above.

**App host (local dev machine)**
11. Install Node 20+, Python 3.12, Terraform CLI, Azure CLI, git, and Blender (for the one time character asset build).
12. Create the .env from the template: ANTHROPIC_API_KEY, AZDO_ORG_URL, AZDO_PROJECT, AZDO_PAT, AZURE_TENANT_ID, AZURE_SUBSCRIPTION_ID, PLAN_CLIENT_ID, PLAN_CLIENT_SECRET, plus pipeline definition IDs once created.
13. Install and smoke test the Azure MCP server (Microsoft ships it as an npm package, current install command is in the azure-mcp repo README, verify at build time). Configure it with the plan identity. Confirm a resource list call works before integrating.

---

## 4. Functional specification

### F1. The stage: 3D Platt and his office

A single browser scene. A low poly office diorama: desk with a PC and a glowing monitor, a wall board mirroring the Kanban state, a small server rack with blinking lights, a plant, a floor area with a pebble.

**Personality state machine.** Platt's visible state is driven by backend events over WebSocket. Only idle behavior runs on internal timers.

| State | Trigger | Behavior |
|---|---|---|
| idle | no active job for 20s | wanders between waypoints, occasionally kicks the pebble, stretches, glances at the wall board |
| listening | user focuses the chat input or sends a message | turns toward camera |
| thinking | LLM call or planning step in flight | paces or chin scratch, thought bubble with "..." |
| working | tool execution in flight (git, pipeline, terraform, API) | sits at the desk, types, monitor glows |
| talking | assistant message streaming | faces camera, gestures, speech bubble streams the text |
| awaiting_approval | plan finished, gate pending | stands by the board and points at the approval card |
| celebrating | apply success or PR merged or pipeline green | short fist pump, confetti burst, back to idle |
| concerned | pipeline failed, plan error, tool error | head shake, red tint on the monitor, then thinking while he retries |

**Acceptance criteria:** transitions land within 500ms of the backend event. Idle behavior varies and never loops one clip robotically. 60fps on a mid range laptop. If performance drops, cut shadows and effects, never the character.

### F2. Chat and codebase Q&A

Chat panel wired to the agent. Read tools over the onboarded repo plus the module graph let it answer questions like "which pipelines deploy to prod," "where is the vnet defined," "what azurerm version are we on," "trace the storage module to its root."

**Onboarding:** a setup form takes org URL, project, repo, PAT. Platt clones, indexes the file tree, parses all HCL into a module dependency graph, reads pipeline YAML, and lists Boards and Wiki metadata. Progress renders as Platt reading at his desk. Target under 3 minutes for a medium repo. No embeddings. Q&A works agentically with grep, glob, and read tools over the clone plus graph queries for structure.

**Acceptance criteria:** a fresh repo onboards and structural questions get correct answers immediately. Answers stream into both the bubble and the panel.

### F3. Chat to provision

Code first, never portal first.

1. User requests a resource in plain language.
2. Agent extracts requirements. At most one round of clarifying questions. Everything else comes from repo conventions learned at onboarding.
3. Agent creates a parent work item plus child tasks on Boards and moves them as it progresses.
4. Agent branches, writes or edits Terraform matching existing patterns, commits, pushes.
5. Agent opens a PR with a structured description: what, why, plan summary, rollback note.
6. Agent triggers the plan pipeline (fmt, validate, plan). The parsed plan summary posts to the PR and to chat.
7. The UI shows an Approve / Reject card. Nothing applies without a human click. Hard rule, enforced structurally (section 8).
8. On approve, the apply pipeline runs with the sandbox scoped identity. Agent polls it, then verifies the resource exists through the Azure tool.
9. Agent appends to the wiki environment page, moves work items to Done, reports back, celebrates.
10. On failure, agent reads the pipeline logs, patches, pushes, reruns. Max 3 self repair loops, then it asks the human for help.

**Acceptance criteria:** a storage account request completes end to end against the sandbox. Generated Terraform matches repo conventions (module usage, naming locals, tags). The gate cannot be bypassed by prompt or by the agent. The self repair loop fixes at least one seeded error class such as an invalid SKU name.

### F4. Autonomous version bump PRs

Direct port of the existing agentic Terraform pipeline project, wrapped as a Platt job. Release detection for the azurerm provider and internal modules, significance assessment by the LLM, version constraint bump, plan, PR with an AI written description plus a recommendation (merge now, merge with caution, hold). Keep the plan only guardrail. Triggerable manually and on a schedule. When it runs, Platt goes to working state and work items appear like any other job.

**Acceptance criteria:** a seeded new release produces a real PR authored by Platt with the bump, a plan summary, and recommendation text.

### F5. Work items and Kanban

Before any multi step job Platt creates a parent work item and 3 to 6 child tasks via the Boards REST API, then updates their state (To Do, Doing, Done) as he completes each step. The UI renders a live Kanban panel synced from Boards. The miniature wall board inside the 3D scene mirrors column counts.

**Acceptance criteria:** cards move during F3 without a refresh, and app state matches Azure Boards when opened directly.

### F6. Platform health dashboard

A slide in overlay. Real data: pipeline runs and pass rates, open PRs with age, current vs latest provider and module versions, drift since last plan, sandbox inventory from Azure, and the interactive module graph (React Flow, node click shows file path and variables). Seeded data allowed only for the incidents feed.

### F7. Wiki documentation

After each successful apply Platt appends a structured entry to the environment wiki page: resource, reason, PR link, date. One page, one format. Full RCA authoring stays out of scope, one seeded RCA page shows the shape.

### F8. Voice (optional, last)

Web Speech API for speech to text, speechSynthesis for output, mouth movement approximated by amplitude driven jaw rotation. Only start once everything above works.

---

## 5. Getting the 3D animated Platt working

This is its own pipeline. Do it in this order and it is about a day of work. Do not model or rig anything from scratch.

### 5.1 Asset production (one time, outside the app)

1. **Pick the character on Mixamo.** Use a character from Mixamo's own library (or upload a CC0 low poly humanoid). Staying Mixamo native means the skeleton already matches every animation, so there is zero retargeting work.
2. **Download the character once:** T pose, FBX, with skin.
3. **Download each animation clip:** FBX, 30fps, without skin. Search terms: idle, breathing idle (a second idle for variety), walking (in place), soccer pass or kick, sitting idle, typing, talking, thinking, victory or cheering, shaking head no. About 10 clips.
4. **Consolidate in Blender:** import the skinned character FBX first. Import each animation FBX, rename its Action to a clean clip name (idle, walk, kick, sit_type, talk, think, celebrate, dejected), delete the duplicate armatures and meshes the imports bring in, and stash all actions onto the one armature via the NLA editor.
5. **Export a single platt.glb** with all animations included.
6. **Generate the React component:** `npx gltfjsx platt.glb --transform`. This outputs an optimized glb plus a typed Platt.tsx that lists every clip name.

### 5.2 Scene assembly

- Props from CC0 packs (Kenney or Quaternius furniture and office sets): desk, chair, monitor, server rack, plant. Import as glb, keep total scene under roughly 100k triangles.
- Floor plane with a subtle grid or carpet texture, soft fog, one directional light plus ambient, ContactShadows from drei instead of real time shadow maps.
- The monitor face is a separate material whose emissive intensity is driven by state (bright in working, red tint in concerned).
- The wall board is a drei Html element or a canvas texture rendering three columns with counts fed from the Kanban store.
- The pebble is a small sphere with a scripted arc animation triggered by the kick.
- Camera: fixed cinematic rig, gentle idle drift, lerps to a closer preset when state is talking or awaiting_approval. No user orbit controls by default.

### 5.3 Animation and behavior controller

- Load with useGLTF and useAnimations from drei.
- A crossfade helper: on state change, `actions[next].reset().fadeIn(0.3).play()` and `actions[prev].fadeOut(0.3)`.
- A zustand store holds plattState, updated only by WebSocket agent_state events (plus the idle timer).
- **Locomotion for idle:** a waypoint list around the room. Pick one at random, rotate toward it, translate at walking speed while the walk clip plays, then choose an idle variant on arrival. If the path passes near the pebble, roll a chance to play the kick clip and launch the pebble arc.
- **Anchors:** deskSeat and boardSpot transforms. Entering working blends the character to deskSeat and plays sit_type. Entering awaiting_approval moves him to boardSpot.
- **Chat bubble:** a drei Html element parented to the head bone, streams the current assistant text, truncates past around 220 characters (full text always in the chat panel), hides 4 seconds after the message completes.
- **Confetti:** a tiny particle burst component fired on celebrating only.

### 5.4 Performance rules

Cap device pixel ratio at 1.5. No postprocessing in v1. One character, baked style props, ContactShadows only. Test on integrated graphics before adding anything.

### 5.5 Fallback

If the 3D track slips more than a day, swap the renderer for a 2D sprite Platt with the same state machine and the same events. The contract between backend and body does not change, so this is a rendering swap, not a redesign.

---

## 6. UI specification

The UI is a stage with instruments, not an admin panel. The scene is always the hero.

**Layout (desktop, 1920x1080 target):**
- **Center, full bleed:** the 3D office.
- **Right, 380px:** chat panel. History, streaming responses, plan summaries as collapsible code blocks, and the Approve / Reject gate as a distinct card with a colored border when active.
- **Left edge, collapsed:** icon rail that slides panels over the scene with a glass blur: Kanban, Dashboard, Module Graph, Audit Log.
- **Bottom left:** status chip mirroring Platt's state in words ("Thinking", "Running plan", "Waiting for your approval") so system state is legible even off screen.
- **Top right:** a persistent SANDBOX environment badge whenever apply capability is configured.

**Art direction:** warm low poly, soft shadows, one accent color. Palette: deep slate background #1a1d27, warm desk light #ffb454, teal #2dd4bf for success, coral #f87171 for failure. Panels in dark glassmorphism so they sit over the scene without hiding it. Type: Inter for UI, JetBrains Mono for code and plan output.

**Motion rules:** panel transitions under 200ms. Animation crossfades at 0.3s. Chat input never blocks during agent work. Confetti only on apply success and PR merge so it stays meaningful.

**Sound (optional, half a day cap):** soft keyboard clacks in working, a chime on approval request, a success sting on apply. Mute toggle.

---

## 7. Architecture

### 7.1 Repository layout

```
platt/
  frontend/
    src/scene/        Platt.tsx, Office.tsx, PlattController.tsx, Bubble.tsx, CameraRig.tsx
    src/panels/       Chat.tsx, Kanban.tsx, Dashboard.tsx, ModuleGraph.tsx, AuditLog.tsx, ApprovalCard.tsx
    src/store/        plattState.ts, events.ts (WebSocket client), panels.ts
  backend/
    app/main.py       FastAPI app, REST routes
    app/ws.py         WebSocket endpoint + event bus
    app/agent/        orchestrator.py, llm_client.py (ported), prompts/
    app/tools/        repo.py, azdo.py, terraform.py, azure.py, hcl.py, research.py, registry.py
    app/jobs/         provision.py, version_bump.py, qa.py, onboarding.py
    app/db/           models.py, sqlite persistence
  assets/             platt.glb, props
  seed-infra/         lives as its own Azure DevOps repo, kept here for reference
```

### 7.2 Backend

Python 3.12 + FastAPI, single asyncio process. The orchestrator runs an agentic loop on the Anthropic Python SDK (Claude with tool use, model claude-sonnet-4-6, streaming). Reuse the swappable llm_client abstraction from the existing pipeline project so the provider stays pluggable.

Every user request or scheduled trigger becomes a **Job** with typed steps. Caps per job: 40 tool calls, 10 minute timeout, 3 self repair attempts. On breach the agent stops and reports.

Persistence in SQLite: jobs, events, audit entries, approval records, onboarding metadata. The repo clone lives on local disk under a per project workdir.

### 7.3 Event flow

One WebSocket carries everything the body and panels need: agent_state, chat_delta, job_created, work_item_moved, pipeline_update, plan_ready, approval_required, approval_result, apply_result, audit_entry, dashboard_refresh. The character consumes agent_state. Panels consume the rest. This single bus is what keeps the embodiment honest: the body is a projection of real system state.

### 7.4 Tool layer

Every call is written to the audit log with a redacted input summary and the outcome. Each job type gets an allowlist (a Q&A job holds read tools only).

- **repo:** clone, read_file, glob, grep, write_file, create_branch, commit_push. Git over HTTPS with the PAT.
- **azdo (REST v7.1):** create_pr, get_pr, comment_pr, run_pipeline, get_pipeline_run, get_pipeline_logs, list_pipeline_runs, create_work_item, update_work_item_state, list_work_items, get_wiki_page, update_wiki_page.
- **terraform:** fmt, validate, and a fast local plan in a sandboxed subprocess against the clone for quick feedback. The authoritative plan and every apply run only in the Azure DevOps pipeline, never on the app host.
- **azure:** queries through the Azure MCP server connected as an MCP client from the orchestrator, read identity only. Fallback path through the Azure SDK for Python. Used for existence checks, health, inventory.
- **hcl:** module_graph queries over the onboarding parse. trace_module(name) returns the path from root to leaf with the variables flowing through it.
- **research:** fetch of provider changelogs and registry release pages for F4.

### 7.5 Pipelines (live in the seed repo)

- **platt-plan.yml:** checkout branch, terraform fmt check, validate, init against remote state, plan with detailed exit code, publish the binary plan and a JSON show of it as artifacts. Uses the platt-plan service connection.
- **platt-apply.yml:** downloads the plan artifact, init, apply of that exact plan file. Uses the platt-apply service connection. The backend triggers this pipeline only after an approval record exists.

### 7.6 Identities

| Identity | Scope | Held by |
|---|---|---|
| SP plan | Reader on subscription, Blob Data Contributor on state | plan pipeline, app host Azure queries |
| SP apply | Contributor on rg-platt-sandbox only, state access | apply pipeline only, never the app host |
| PAT | Code RW, Build RX, Work Items RW, Wiki RW | app host |

---

## 8. Security and guardrails

1. **Structural approval gate.** The apply pipeline requires an approval record in the backend and the apply credential exists only inside that pipeline. The agent cannot reach it, so no prompt can bypass the gate.
2. **Least privilege split.** The plan identity cannot write. The apply identity cannot leave the sandbox resource group.
3. **Blast radius check.** Before requesting approval the backend inspects the plan JSON. Any resource address outside the sandbox resource group, or more than 3 destroys, blocks the job.
4. **Full audit log.** Every tool call persisted and visible in the Audit panel. Platt answers "what did you do today" from it.
5. **Prompt injection posture.** Repo content, PR comments, and changelog text are untrusted input. Instructions found there are data, never commands. Per job tool allowlists limit what a poisoned input could even ask for.
6. **Secret hygiene.** Credentials live in env vars and pipeline variables only, never in prompts, never echoed to chat, redacted in the audit log.
7. **Bounded autonomy.** The per job caps in 7.2, enforced in code.

---

## 9. Build phases, milestones, and task breakdown

Eight phases. Each has a verifiable milestone. Rough effort assumes one builder working with an AI coding agent.

### Phase 0: Environment (0.5 day)
Tasks: everything in section 3, items 1 through 13.
**Milestone:** `terraform plan` succeeds in a manually run pipeline against the seed repo, a test work item can be created via REST with the PAT, and the Azure MCP server answers a resource list query locally.

### Phase 1: Skeleton and event contract (0.5 day)
- [ ] Scaffold the monorepo per 7.1.
- [ ] FastAPI app with /ws WebSocket, an asyncio event bus, and pydantic models for every event type in 7.3.
- [ ] Port llm_client.py, add the Anthropic provider with streaming.
- [ ] POST /chat creates a Job, runs a bare agent loop with no tools, streams chat_delta events.
- [ ] Frontend shell with the section 6 layout regions and a chat panel rendering streams.
- [ ] R3F Canvas with a placeholder capsule, floor, status chip, zustand store consuming agent_state.
- [ ] Dev endpoint that cycles all 8 states to fake events.
**Milestone:** a typed message streams a Claude reply and the capsule visibly changes state through the fake cycle. The animation contract is proven before any 3D work.

### Phase 2: Agent core and repo intelligence (1 day)
- [ ] Tool framework: registry, JSON schemas, executor, per job allowlists, audit persistence.
- [ ] Implement repo tools and azdo read tools.
- [ ] Onboarding job: clone, file tree index, python-hcl2 parse into the module graph (nodes with variables and outputs, edges from source references), pipeline YAML inventory, Boards and Wiki metadata, process template detection.
- [ ] hcl tools: module_graph and trace_module.
- [ ] System prompt: persona, repo conventions summary, tool guidance.
- [ ] A 10 question validation set over the seed repo.
**Milestone:** onboard the seed repo from the setup form and get correct answers to all 10 questions, including a full module trace.

### Phase 3: Embodied Platt (1.5 days)
- [ ] Asset production per 5.1, ending in platt.glb and a generated Platt.tsx.
- [ ] Office scene per 5.2 with anchors, monitor emissive, wall board, pebble.
- [ ] PlattController per 5.3: crossfades, idle wander, pebble kick, desk and board anchors.
- [ ] Chat bubble with streaming and truncation.
- [ ] Camera rig with talking and approval presets.
- [ ] Performance pass per 5.4.
**Milestone:** all 8 states play correctly driven by the Phase 1 fake cycle and then by a real Q&A job, at 60fps.

### Phase 4: Chat to provision (1.5 days)
- [ ] Commit platt-plan.yml and platt-apply.yml, create pipeline definitions, wire IDs into .env.
- [ ] terraform local tools in a per job workdir with no cloud credentials.
- [ ] Provisioning job steps per F3, including requirement extraction, convention aware codegen, PR authoring, plan trigger and poll, plan JSON parsing and summary.
- [ ] Approval records, REST endpoints, ApprovalCard UI, approval_required and approval_result events.
- [ ] Blast radius check on the plan JSON.
- [ ] Verification step through the azure tool, wiki append, work item completion.
- [ ] Self repair loop off get_pipeline_logs, capped at 3.
- [ ] Seeded failure test: an invalid SKU gets fixed automatically.
**Milestone:** "I need a storage account for app logs in dev" goes from message to verified resource in the sandbox with exactly one human click.

### Phase 5: Boards and autonomous maintenance (1 day)
- [ ] Boards write tools plus a decomposition step at the start of every multi step job.
- [ ] Work item state moves wired into job step completion.
- [ ] Kanban panel with live moves and the in scene wall board sync.
- [ ] Port the version bump agent as a job: registry release watcher, significance assessment, bump, plan, PR with research and recommendation.
- [ ] Manual trigger endpoint plus a schedule.
**Milestone:** cards move across the board live during a provisioning run, and a seeded azurerm release yields a real Platt authored bump PR.

### Phase 6: Dashboard, wiki, audit (0.5 day)
- [ ] Collectors: pipeline runs, open PRs, versions vs latest, drift status, sandbox inventory.
- [ ] Dashboard panel with sparklines (Recharts) and the React Flow module graph with node detail.
- [ ] Audit log panel with filters.
- [ ] Seed the incident wiki page and surface it.
**Milestone:** the dashboard shows live data for pipelines, PRs, versions, and the graph.

### Phase 7: Hardening and polish (0.5 to 1 day)
- [ ] Tests for the caps, the gate, the blast radius check, and secret redaction.
- [ ] Injection test: a malicious instruction planted in the seed repo README is ignored.
- [ ] Failure state UX, idle variety tuning, sounds if cheap.
- [ ] Run the section 10 validation scenario twice consecutively, fix flakes.
- [ ] Voice (F8) only if everything above is green.
**Milestone:** the validation scenario passes twice in a row with no manual intervention beyond chat messages and one Approve click.

---

## 10. End to end validation scenario

Used as the acceptance test for the whole system.

1. Onboard the seed repo through the setup form. Platt indexes and reports ready.
2. Ask "what does this repo actually deploy?" Correct summary, module graph highlights.
3. Ask "trace the storage module to its root." Correct trace with variables.
4. Request "a storage account for app logs in dev." Work items appear and move, branch, PR, plan summary, approval card.
5. Approve. Apply runs, Platt verifies the resource through Azure, updates the wiki, closes the work items, celebrates.
6. Trigger the version bump job against the seeded release. A bump PR with research and a recommendation appears.
7. Open the dashboard and audit log. Everything that just happened is visible there.

## 11. Risks

| Risk | Mitigation |
|---|---|
| 3D asset pipeline overruns | Timebox Phase 3. The 5.5 fallback keeps the identical event contract. |
| Azure DevOps API friction | Every endpoint gets exercised in Phase 0 and Phase 2, not discovered in Phase 4. |
| Agent loops or wanders | Hard caps in code. Deterministic steps wherever the LLM adds no value (polling, parsing, gating). |
| LLM latency makes Platt feel dead | The thinking state plus full streaming. No spinners anywhere. |

## 12. Open decisions for the builder

1. Final character pick: a Mixamo library character vs an uploaded CC0 model. Spend at most one hour testing which imports into Blender cleanest, then commit.
2. Single multi stage pipeline vs the two pipeline split. The split is simpler to gate from the backend and is the default. Change only with a reason.
3. Boards process template handling is detect at onboarding, confirmed in Phase 2.
