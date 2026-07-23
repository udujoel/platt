import type { ThreeStageState } from "../three-stage-pose";
import type { Vector3Tuple } from "./types";

export type CameraPreset = { position: Vector3Tuple; fov: number };

/**
 * Fixed close framing for the compact desk-nook widget (PlattDeskWidget). Tuned much tighter
 * than the full-room `camera-presets.ts` pair since the whole scene here is a single cropped
 * desk corner, not a walkable room.
 */
export const DESK_CAMERA_DEFAULT: CameraPreset = { position: [0.15, 1.62, 2.7], fov: 32 };
export const DESK_CAMERA_TALK: CameraPreset = { position: [0.1, 1.58, 2.35], fov: 28 };

export const DESK_CAMERA_DAMP_LAMBDA = 3;
export const DESK_IDLE_DRIFT_AMPLITUDE = 0.045;
export const DESK_IDLE_DRIFT_SPEED = 0.22;

/** Subtle zoom-in while talking/awaiting approval; otherwise the fixed default desk framing. */
export function deskCameraPresetForState(state: ThreeStageState): CameraPreset {
  return state === "talking" || state === "awaiting_approval" ? DESK_CAMERA_TALK : DESK_CAMERA_DEFAULT;
}
