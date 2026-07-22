import type { ThreeStageState } from "../three-stage-pose";
import type { CrossfadePlan, PlattClipName } from "./types";

/** Fallback used only when a state is somehow missing from `STATE_FADE_SECONDS`. */
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

/**
 * Per-state crossfade duration (seconds), tuned by feel rather than one blanket 0.3s: reactive
 * states (talking, celebrating) fade quickly so they read as immediate, grounded states (working,
 * awaiting_approval) fade slower so sitting down doesn't look like a jump cut, and idle/listening
 * sit in between.
 */
const STATE_FADE_SECONDS: Record<ThreeStageState, number> = {
  idle: 0.4,
  listening: 0.35,
  thinking: 0.3,
  working: 0.45,
  talking: 0.18,
  awaiting_approval: 0.45,
  celebrating: 0.15,
  concerned: 0.25,
};

export function clipForState(state: ThreeStageState): PlattClipName {
  return STATE_CLIPS[state];
}

function fadeSecondsForState(state: ThreeStageState): number {
  return STATE_FADE_SECONDS[state] ?? CROSSFADE_DURATION_SECONDS;
}

/**
 * Selects the clip crossfade for a state transition, per PRD 5.3:
 * `actions[next].reset().fadeIn(d).play()` / `actions[prev].fadeOut(d)`. Each side eases on its
 * own state's tuned duration (`STATE_FADE_SECONDS`) so, e.g., snapping into "celebrating" fades in
 * fast regardless of how slowly the outgoing state prefers to fade out.
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
    fadeOutSeconds: previous ? fadeSecondsForState(previous) : 0,
    fadeInSeconds: fadeSecondsForState(next),
  };
}
