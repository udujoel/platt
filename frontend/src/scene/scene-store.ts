import { create } from "zustand";
import type { ThreeStageState } from "../three-stage-pose";
import type { Vector3Tuple } from "./types";

export type BoardColumns = [number, number, number];

export type PlattSceneState = {
  state: ThreeStageState;
  speech: string;
  boardColumns: BoardColumns;
  pebbleKickAt: number | null;
  /** Raw 0..1 TTS amplitude (PRD F8), read by `PlattController` each frame and handed to the character rig. */
  jawAmplitude: number;
  /**
   * Live world anchor (x, y, z) of the character rig, published by `PlattController` each frame
   * (currently only wired for the pose-driven states; idle wander is not yet published here — see
   * `Bubble.tsx`, which falls back to the pose approximation while this is null). Lets subtree
   * consumers like the speech bubble follow the rig without prop drilling through the Canvas tree.
   */
  headAnchor: Vector3Tuple | null;
  setState: (state: ThreeStageState) => void;
  setSpeech: (speech: string) => void;
  setBoardColumns: (columns: BoardColumns) => void;
  triggerPebbleKick: (elapsedSeconds: number) => void;
  setJawAmplitude: (amplitude: number) => void;
  setHeadAnchor: (anchor: Vector3Tuple | null) => void;
};

/**
 * Internal scene plumbing (per PRD 5.2/5.3): the external event-state contract in `main.tsx`
 * stays the single source of truth and is synced in via `ThreeOfficeScene`'s props each render;
 * this store just lets scene subtree components (monitor emissive, board columns, bubble) read
 * that state without prop drilling through the Canvas tree.
 */
export const usePlattSceneStore = create<PlattSceneState>((set) => ({
  state: "idle",
  speech: "",
  boardColumns: [0, 0, 0],
  pebbleKickAt: null,
  jawAmplitude: 0,
  headAnchor: null,
  setState: (state) => set({ state }),
  setSpeech: (speech) => set({ speech }),
  setBoardColumns: (boardColumns) => set({ boardColumns }),
  triggerPebbleKick: (pebbleKickAt) => set({ pebbleKickAt }),
  setJawAmplitude: (jawAmplitude) => set({ jawAmplitude }),
  setHeadAnchor: (headAnchor) => set({ headAnchor }),
}));
