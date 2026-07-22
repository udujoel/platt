# Platt Backlog

Living list of remaining/future work. Core F1–F8 is built and shipped to `main` (26 PRs).

## In progress
- **Wave 7 — UI + character polish** (requested 2026-07-22): refine the character's movement and
  look, and the scene/space + UI. See "Polish" below.

## Polish — UI, character, and space (wave 7)
- **Character movement:** more natural idle wander (varied waypoints, pauses, weight shift), smoother
  locomotion + turning, better gesture crossfade timing, believable jaw/talk motion, non-robotic
  idle variety (no single looping clip).
- **Character look:** improve the procedural rig proportions/materials/joints so it reads well until
  the real `platt.glb` lands (rounder joints, better silhouette, subtle shading, contact with floor).
- **Scene / space:** warmer low-poly art direction per PRD §6 — lighting + soft fog + ContactShadows,
  desk/monitor/board/server-rack/plant props, monitor emissive tied to state, floor grid/carpet,
  cinematic camera rig with gentle idle drift and talk/approval presets, pebble arc polish.
- **UI:** dark glassmorphism panels over the scene, one warm accent, Inter + JetBrains Mono type,
  panel transitions <200ms, status chip legibility, SANDBOX badge, icon-rail refinement, chat/plan
  block styling. Keep the 3D scene the hero.

## Needs user input / live infrastructure (cannot be done autonomously)
- **Live cloud provision run** (real F3 acceptance) — needs Azure DevOps + Azure Phase-0
  (org/project/PAT, sandbox sub + SP-plan/SP-apply, pipeline defs) as env vars.
- **Real F6 dashboard collectors** — replace clearly-marked seeded data with live AzDO/Azure data.
- **Real `platt.glb` character asset** — one-time Mixamo → Blender → gltfjsx export per
  `frontend/src/scene/ASSETS.md`; code falls back to the procedural rig until then.

## Later / optional
- Sound design (keyboard clacks in `working`, approval chime, apply success sting; mute toggle).
- Deeper F7 wiki/RCA authoring beyond the structured environment-page append.
- Multi-instance/production-scale hardening (currently single Neon + SSE, fine for the slice).
