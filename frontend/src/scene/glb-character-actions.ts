import type { CrossfadePlan, PlattClipName } from "./types";

/** Minimal shape of a `three` `AnimationAction` this module drives — matches drei's `useAnimations` output. */
export type MixamoAction = {
  reset: () => MixamoAction;
  fadeIn: (duration: number) => MixamoAction;
  fadeOut: (duration: number) => MixamoAction;
  play: () => MixamoAction;
};

export type MixamoActionMap = Partial<Record<PlattClipName, MixamoAction | null | undefined>>;

/**
 * Runs a `CrossfadePlan` against a `useAnimations()` action map per PRD 5.3:
 * `actions[to].reset().fadeIn(d).play()` while `actions[from].fadeOut(d)`. Missing actions
 * (clip not present in the glb, e.g. during a partial export) are skipped rather than throwing,
 * since the crossfade plan drives PRD clip names that may not all exist in every asset revision.
 */
export function applyCrossfadePlan(actions: MixamoActionMap, plan: CrossfadePlan): PlattClipName {
  const { fadeOutClip, fadeInClip, fadeOutSeconds, fadeInSeconds } = plan;

  if (fadeOutClip && fadeOutClip !== fadeInClip) {
    actions[fadeOutClip]?.fadeOut(fadeOutSeconds);
  }
  actions[fadeInClip]?.reset().fadeIn(fadeInSeconds).play();

  return fadeInClip;
}
