import { describe, expect, it, vi } from "vitest";

import { applyCrossfadePlan, type MixamoAction, type MixamoActionMap } from "./glb-character-actions";
import type { CrossfadePlan } from "./types";

function mockAction(): MixamoAction {
  const action = {
    reset: vi.fn(() => action),
    fadeIn: vi.fn(() => action),
    fadeOut: vi.fn(() => action),
    play: vi.fn(() => action),
  };
  return action;
}

describe("applyCrossfadePlan", () => {
  it("resets, fades in, and plays the target clip's action", () => {
    const sitType = mockAction();
    const actions: MixamoActionMap = { sit_type: sitType };
    const plan: CrossfadePlan = { fadeOutClip: null, fadeInClip: "sit_type", fadeOutSeconds: 0, fadeInSeconds: 0.3 };

    applyCrossfadePlan(actions, plan);

    expect(sitType.reset).toHaveBeenCalledTimes(1);
    expect(sitType.fadeIn).toHaveBeenCalledWith(0.3);
    expect(sitType.play).toHaveBeenCalledTimes(1);
  });

  it("fades out the previous clip's action alongside fading in the next", () => {
    const idle = mockAction();
    const sitType = mockAction();
    const actions: MixamoActionMap = { idle, sit_type: sitType };
    const plan: CrossfadePlan = {
      fadeOutClip: "idle",
      fadeInClip: "sit_type",
      fadeOutSeconds: 0.3,
      fadeInSeconds: 0.3,
    };

    applyCrossfadePlan(actions, plan);

    expect(idle.fadeOut).toHaveBeenCalledWith(0.3);
    expect(sitType.reset).toHaveBeenCalledTimes(1);
    expect(sitType.fadeIn).toHaveBeenCalledWith(0.3);
  });

  it("does not fade out when fadeOutClip is null (first mount)", () => {
    const sitType = mockAction();
    const actions: MixamoActionMap = { sit_type: sitType };
    const plan: CrossfadePlan = { fadeOutClip: null, fadeInClip: "sit_type", fadeOutSeconds: 0, fadeInSeconds: 0.3 };

    applyCrossfadePlan(actions, plan);

    expect(sitType.fadeOut).not.toHaveBeenCalled();
  });

  it("skips fading out an action that is the same as the incoming clip", () => {
    const idleBreathe = mockAction();
    const actions: MixamoActionMap = { idle_breathe: idleBreathe };
    const plan: CrossfadePlan = {
      fadeOutClip: "idle_breathe",
      fadeInClip: "idle_breathe",
      fadeOutSeconds: 0,
      fadeInSeconds: 0,
    };

    applyCrossfadePlan(actions, plan);

    expect(idleBreathe.fadeOut).not.toHaveBeenCalled();
    expect(idleBreathe.reset).toHaveBeenCalledTimes(1);
  });

  it("tolerates a clip missing from the action map (glb without that export) without throwing", () => {
    const actions: MixamoActionMap = {};
    const plan: CrossfadePlan = { fadeOutClip: "idle", fadeInClip: "celebrate", fadeOutSeconds: 0.3, fadeInSeconds: 0.3 };

    expect(() => applyCrossfadePlan(actions, plan)).not.toThrow();
  });

  it("returns the fade-in clip so callers can update currentClip", () => {
    const actions: MixamoActionMap = { kick: mockAction() };
    const plan: CrossfadePlan = { fadeOutClip: null, fadeInClip: "kick", fadeOutSeconds: 0, fadeInSeconds: 0.3 };

    expect(applyCrossfadePlan(actions, plan)).toBe("kick");
  });
});
