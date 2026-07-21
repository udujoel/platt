# `platt.glb` asset pipeline

`PlattCharacter` (see `PlattCharacter.tsx`) looks for an animated character at
`frontend/public/platt.glb` and drives it with drei's `useGLTF` + `useAnimations`
(`PlattCharacterGLB.tsx`). If that file is missing, fails to fetch, or fails to parse, the scene
falls back to the procedural box rig (`ProceduralPlatt.tsx`) automatically — nothing breaks, but
you also don't get the real character until this pipeline is run once, manually, by a human.

There is no way to script the Mixamo/Blender steps below; they require the Mixamo web UI and the
Blender GUI. This doc is the runbook for whoever does that.

## 1. Pick a Mixamo character

1. Go to [mixamo.com](https://www.mixamo.com) (Adobe account required) and pick a character model
   from the **Characters** tab. Anything human-rigged works; a plain/neutral character reads best
   at the small on-screen scale Platt renders at.
2. Download the character alone once, as **FBX Binary (.fbx)**, T-pose, no animation — this is the
   base mesh + skeleton every clip below gets retargeted onto.

## 2. Download the ~10 PRD clips

For each clip name in `PlattClipName` (`frontend/src/scene/types.ts`), find a matching Mixamo
animation and download it **FBX for Unity** (skin unchecked, since the skeleton already came down
with the base character) at 30fps, with the same character selected so the retargeting matches:

| `PlattClipName` | Suggested Mixamo search |
| --- | --- |
| `idle` | "Idle" |
| `idle_breathe` | "Breathing Idle" |
| `walk` | "Walking" |
| `kick` | "Soccer Idle Kick" / "Kicking" |
| `sit_type` | "Sitting Typing" |
| `talk` | "Talking" |
| `think` | "Thinking" |
| `celebrate` | "Cheering" / "Victory" |
| `dejected` | "Defeated" / "Sad Idle" |

Save each download as `<clipname>.fbx` (e.g. `sit_type.fbx`) so the Blender step below can name the
resulting action to match.

## 3. Consolidate in Blender

Mixamo gives you one FBX per clip, each with its own copy of the mesh/skeleton. Blender is used to
merge them into a single rig with multiple named actions, which is what `useAnimations` expects.

1. Open a new Blender scene, delete the default cube.
2. **File → Import → FBX**, import the base character FBX first.
3. For each clip FBX, import it into the *same* scene, then:
   - In the **Action Editor** (or NLA editor), locate the newly-imported armature's action.
   - Rename that action to the exact `PlattClipName` string (e.g. `sit_type`, `celebrate`) — this
     name becomes the `actions["sit_type"]` key `useAnimations` exposes at runtime, and is what
     `glb-character-actions.ts` looks up.
   - Push the action onto the base armature (Blender re-imports a full armature+mesh per FBX; use
     **Object → Animation → Make Single User** or manually copy the action's F-curves onto the base
     armature, then delete the duplicate armature/mesh so only one skinned mesh remains).
4. Once all clips are actions on the single base armature, verify each plays back correctly by
   scrubbing the timeline with each action assigned.
5. Apply any needed scale/rotation fixes (Mixamo characters commonly need a 0.01 scale + -90°
   X-rotation correction) and **apply all transforms** (Ctrl+A → All Transforms) before export, so
   the glb doesn't carry a stray transform that fights the `PlattCharacterGLB` rig group.

## 4. Export the glb

**File → Export → glTF 2.0 (.glb)**, with:
- Format: `glTF Binary (.glb)`
- Include → check **Animation**, uncheck anything not needed (cameras, lights, punctual lights).
- Compression: off (keep this pipeline simple; revisit Draco/meshopt only if the ~1MB+ file size
  becomes a real problem).

Save as `platt.glb`.

## 5. Inspect with gltfjsx (optional but recommended)

[`gltfjsx`](https://github.com/pmndrs/gltfjsx) generates a typed component + prints the node/action
names it finds, which is the fastest way to confirm the exported clip names match
`PlattClipName` exactly before wiring anything up:

```sh
npx gltfjsx platt.glb --transform
```

This also runs the model through `gltf-transform`'s optimizer (dedup, prune, resize textures),
which is worth doing even though `PlattCharacterGLB.tsx` doesn't use the generated `.tsx` output —
it only cares about the transformed `.glb`. Compare the console's printed animation-clip names
against `PlattClipName` in `frontend/src/scene/types.ts`; rename in Blender and re-export if they
don't match (`useAnimations` keys `actions` off these exact names).

## 6. Place the asset

Copy the final file to:

```
frontend/public/platt.glb
```

`useGLTF("/platt.glb")` in `PlattCharacterGLB.tsx` fetches it from the app's public root — no other
wiring is required. Reload the app; the box rig should be replaced by the real character. If it
isn't, open devtools — a failed fetch or parse error there means the fallback kicked in, which is
expected/safe behavior per `PlattCharacter.tsx`.
