import type React from "react";
import type { ThreeStageState } from "../three-stage-pose";

export type Vector3Tuple = [number, number, number];

/** Clip names match the ~10 Mixamo actions named in PRD 5.1 (`idle, walk, kick, sit_type, talk, think, celebrate, dejected`). */
export type PlattClipName =
  | "idle"
  | "idle_breathe"
  | "walk"
  | "kick"
  | "sit_type"
  | "talk"
  | "think"
  | "celebrate"
  | "dejected";

/** Which clip to fade out of / into, and how long each fade takes (seconds). */
export type CrossfadePlan = {
  fadeOutClip: PlattClipName | null;
  fadeInClip: PlattClipName;
  fadeOutSeconds: number;
  fadeInSeconds: number;
};

/**
 * Contract a `platt.glb` loader must satisfy to drop in for `PlattCharacter` with no
 * controller changes: it runs a crossfade plan and reports which clip is active. Receiving
 * the full plan (not just the target clip) lets a real `useAnimations` implementation fade
 * the outgoing action out while fading the incoming one in, per PRD 5.3.
 */
export type CharacterHandle = {
  readonly currentClip: PlattClipName;
  playClip: (plan: CrossfadePlan) => void;
  /** Raw 0..1 amplitude signal (PRD F8); the rig maps it to a jaw rotation each frame. */
  setJawAmplitude: (amplitude: number) => void;
};

export type PlattCharacterProps = {
  state: ThreeStageState;
  clip: PlattClipName;
  /** When set, overrides the pose-driven x/z anchor (used for idle wander). Mutated per-frame without re-render. */
  anchor?: React.MutableRefObject<Vector3Tuple>;
};
