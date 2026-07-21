import { create } from "zustand";
import type { ThreeStageState } from "../three-stage-pose";

export type BoardColumns = [number, number, number];

export type PlattSceneState = {
  state: ThreeStageState;
  speech: string;
  boardColumns: BoardColumns;
  pebbleKickAt: number | null;
  setState: (state: ThreeStageState) => void;
  setSpeech: (speech: string) => void;
  setBoardColumns: (columns: BoardColumns) => void;
  triggerPebbleKick: (elapsedSeconds: number) => void;
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
  setState: (state) => set({ state }),
  setSpeech: (speech) => set({ speech }),
  setBoardColumns: (boardColumns) => set({ boardColumns }),
  triggerPebbleKick: (pebbleKickAt) => set({ pebbleKickAt }),
}));
