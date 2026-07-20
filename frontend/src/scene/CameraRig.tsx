import React from "react";
import { useFrame, useThree } from "@react-three/fiber";
import { MathUtils, type PerspectiveCamera } from "three";
import { usePlattSceneStore } from "./scene-store";
import {
  CAMERA_DAMP_LAMBDA,
  CAMERA_IDLE_DRIFT_AMPLITUDE,
  CAMERA_IDLE_DRIFT_SPEED,
  cameraPresetForState,
} from "./camera-presets";

/** Fixed cinematic rig with gentle idle drift; lerps to a closer preset for talking/awaiting_approval. No orbit controls. */
export function CameraRig() {
  const camera = useThree((s) => s.camera) as PerspectiveCamera;
  const state = usePlattSceneStore((s) => s.state);

  useFrame(({ clock }, delta) => {
    const preset = cameraPresetForState(state);
    const drift =
      state === "idle" || state === "listening"
        ? Math.sin(clock.getElapsedTime() * CAMERA_IDLE_DRIFT_SPEED) * CAMERA_IDLE_DRIFT_AMPLITUDE
        : 0;

    camera.position.x = MathUtils.damp(camera.position.x, preset.position[0] + drift, CAMERA_DAMP_LAMBDA, delta);
    camera.position.y = MathUtils.damp(camera.position.y, preset.position[1], CAMERA_DAMP_LAMBDA, delta);
    camera.position.z = MathUtils.damp(camera.position.z, preset.position[2], CAMERA_DAMP_LAMBDA, delta);

    if (typeof camera.fov === "number") {
      camera.fov = MathUtils.damp(camera.fov, preset.fov, CAMERA_DAMP_LAMBDA, delta);
      camera.updateProjectionMatrix();
    }
  });

  return null;
}
