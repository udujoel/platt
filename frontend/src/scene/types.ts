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

/**
 * Contract a `platt.glb` loader must satisfy to drop in for `PlattCharacter` with no
 * controller changes: it plays named clips and reports which one is active.
 */
export type CharacterHandle = {
  readonly currentClip: PlattClipName;
  playClip: (clip: PlattClipName) => void;
};

export type PlattCharacterProps = {
  state: ThreeStageState;
  clip: PlattClipName;
  /** When set, overrides the pose-driven x/z anchor (used for idle wander). Mutated per-frame without re-render. */
  anchor?: React.MutableRefObject<Vector3Tuple>;
};
