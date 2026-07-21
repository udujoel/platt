import type { ThreeStageState } from "../three-stage-pose";
import type { Vector3Tuple } from "./types";

export type CameraPreset = { position: Vector3Tuple; fov: number };

const DEFAULT_PRESET: CameraPreset = { position: [0, 3.15, 7.6], fov: 42 };
const CLOSE_PRESET: CameraPreset = { position: [0.3, 2.55, 5.4], fov: 36 };

export const CAMERA_DAMP_LAMBDA = 3;
export const CAMERA_IDLE_DRIFT_AMPLITUDE = 0.12;
export const CAMERA_IDLE_DRIFT_SPEED = 0.25;

/** Cinematic rig lerps to a closer preset for talking/awaiting_approval, per PRD 5.2. */
export function cameraPresetForState(state: ThreeStageState): CameraPreset {
  return state === "talking" || state === "awaiting_approval" ? CLOSE_PRESET : DEFAULT_PRESET;
}
