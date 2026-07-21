import type { ThreeStageState } from "../three-stage-pose";
import type { CrossfadePlan, PlattClipName } from "./types";

export const CROSSFADE_DURATION_SECONDS = 0.3;

const STATE_CLIPS: Record<ThreeStageState, PlattClipName> = {
  idle: "idle",
  listening: "idle_breathe",
  thinking: "think",
  working: "sit_type",
  talking: "talk",
  awaiting_approval: "idle_breathe",
  celebrating: "celebrate",
  concerned: "dejected",
};

export function clipForState(state: ThreeStageState): PlattClipName {
  return STATE_CLIPS[state];
}

/**
 * Selects the clip crossfade for a state transition, per PRD 5.3:
 * `actions[next].reset().fadeIn(0.3).play()` / `actions[prev].fadeOut(0.3)`.
 * No-ops (zero-duration, null fadeOutClip) when the mapped clip doesn't actually change.
 */
export function selectCrossfade(previous: ThreeStageState | null, next: ThreeStageState): CrossfadePlan {
  const fadeInClip = clipForState(next);
  const fadeOutClip = previous ? clipForState(previous) : null;
  if (fadeOutClip === fadeInClip) {
    return { fadeOutClip: null, fadeInClip, fadeOutSeconds: 0, fadeInSeconds: 0 };
  }
  return {
    fadeOutClip,
    fadeInClip,
    fadeOutSeconds: CROSSFADE_DURATION_SECONDS,
    fadeInSeconds: CROSSFADE_DURATION_SECONDS,
  };
}
