import { describe, expect, it, vi } from "vitest";

import { createCharacterHandleRelay } from "./character-handle-relay";
import type { CharacterHandle, CrossfadePlan } from "./types";

function mockCharacterHandle(clip: CharacterHandle["currentClip"]): CharacterHandle {
  return {
    currentClip: clip,
    playClip: vi.fn(),
  };
}

describe("createCharacterHandleRelay", () => {
  it("forwards playClip to the currently attached instance", () => {
    const { handle, attach } = createCharacterHandleRelay("idle");
    const glb = mockCharacterHandle("idle");
    attach(glb);

    const plan: CrossfadePlan = { fadeOutClip: "idle", fadeInClip: "talk", fadeOutSeconds: 0.3, fadeInSeconds: 0.3 };
    handle.playClip(plan);

    expect(glb.playClip).toHaveBeenCalledWith(plan);
  });

  it("replays the last crossfade plan onto a fresh instance after a Suspense swap", () => {
    const { handle, attach } = createCharacterHandleRelay("idle");
    const procedural = mockCharacterHandle("idle");
    attach(procedural);

    const plan: CrossfadePlan = { fadeOutClip: "idle", fadeInClip: "sit_type", fadeOutSeconds: 0.3, fadeInSeconds: 0.3 };
    handle.playClip(plan);

    // Suspense unmounts the fallback (React nulls the ref) then mounts the resolved glb child.
    attach(null);
    const glb = mockCharacterHandle("idle");
    attach(glb);

    expect(glb.playClip).toHaveBeenCalledWith(plan);
  });

  it("replays the last plan again if the error boundary swaps back to the procedural rig", () => {
    const { handle, attach } = createCharacterHandleRelay("idle");
    const glb = mockCharacterHandle("idle");
    attach(glb);

    const plan: CrossfadePlan = { fadeOutClip: "idle", fadeInClip: "celebrate", fadeOutSeconds: 0.3, fadeInSeconds: 0.3 };
    handle.playClip(plan);

    attach(null);
    const procedural = mockCharacterHandle("idle");
    attach(procedural);

    expect(procedural.playClip).toHaveBeenCalledWith(plan);
  });

  it("does not call playClip on attach when no crossfade has run yet", () => {
    const { attach } = createCharacterHandleRelay("idle");
    const glb = mockCharacterHandle("idle");
    attach(glb);

    expect(glb.playClip).not.toHaveBeenCalled();
  });

  it("reports the active instance's currentClip once one is attached", () => {
    const { handle, attach } = createCharacterHandleRelay("idle");
    attach(mockCharacterHandle("think"));

    expect(handle.currentClip).toBe("think");
  });

  it("falls back to the last known clip while no instance is attached", () => {
    const { handle, attach } = createCharacterHandleRelay("idle");
    const plan: CrossfadePlan = { fadeOutClip: "idle", fadeInClip: "walk", fadeOutSeconds: 0.3, fadeInSeconds: 0.3 };
    handle.playClip(plan);

    attach(null);

    expect(handle.currentClip).toBe("walk");
  });
});
