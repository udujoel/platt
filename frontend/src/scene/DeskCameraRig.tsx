import React from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { MathUtils, type PerspectiveCamera } from "three";
import { usePlattSceneStore } from "./scene-store";
import {
  DESK_CAMERA_DAMP_LAMBDA,
  DESK_IDLE_DRIFT_AMPLITUDE,
  DESK_IDLE_DRIFT_SPEED,
  deskCameraPresetForState,
} from "./desk-camera";

/** Fixed close desk-nook rig: gentle idle drift while resting, subtle zoom while talking. No orbit controls. */
export function DeskCameraRig() {
  const camera = useThree((s) => s.camera) as PerspectiveCamera;
  const state = usePlattSceneStore((s) => s.state);

  useFrame(({ clock }, delta) => {
    const preset = deskCameraPresetForState(state);
    const drift =
      state === "idle" || state === "listening"
        ? Math.sin(clock.getElapsedTime() * DESK_IDLE_DRIFT_SPEED) * DESK_IDLE_DRIFT_AMPLITUDE
        : 0;

    camera.position.x = MathUtils.damp(camera.position.x, preset.position[0] + drift, DESK_CAMERA_DAMP_LAMBDA, delta);
    camera.position.y = MathUtils.damp(camera.position.y, preset.position[1], DESK_CAMERA_DAMP_LAMBDA, delta);
    camera.position.z = MathUtils.damp(camera.position.z, preset.position[2], DESK_CAMERA_DAMP_LAMBDA, delta);

    if (typeof camera.fov === "number") {
      camera.fov = MathUtils.damp(camera.fov, preset.fov, DESK_CAMERA_DAMP_LAMBDA, delta);
      camera.updateProjectionMatrix();
    }
  });

  return null;
}
