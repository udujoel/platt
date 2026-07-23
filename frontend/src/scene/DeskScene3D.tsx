import React from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { createWebGLContextLossHandler } from "../stage-renderer";
import type { ThreeStageState } from "../three-stage-pose";
import { usePlattSceneStore } from "./scene-store";
import { DeskOfficeNook } from "./DeskOfficeNook";
import { DeskPlattController } from "./DeskPlattController";
import { DeskCameraRig } from "./DeskCameraRig";
import { DESK_CAMERA_DEFAULT } from "./desk-camera";

function DeskContextLossGuard({ onContextLost }: { onContextLost: () => void }) {
  const gl = useThree((s) => s.gl);

  React.useEffect(() => {
    const canvas = gl.domElement;
    const handleContextLoss = createWebGLContextLossHandler(onContextLost);
    canvas.addEventListener("webglcontextlost", handleContextLoss);
    return () => canvas.removeEventListener("webglcontextlost", handleContextLoss);
  }, [gl, onContextLost]);

  return null;
}

function DeskWorld({ state }: { state: ThreeStageState }) {
  return (
    <>
      <color attach="background" args={["#161c26"]} />
      <fog attach="fog" args={["#161c26", 3, 6]} />
      <ambientLight intensity={0.95} />
      <directionalLight position={[1.1, 2.2, 1.4]} intensity={1.05} />
      <pointLight
        position={[0.85, 1.05, -0.35]}
        color={state === "concerned" ? "#f87171" : "#ffb454"}
        intensity={state === "working" ? 7 : 4}
        distance={2.2}
      />
      <DeskOfficeNook />
      <DeskPlattController />
      <DeskCameraRig />
    </>
  );
}

/**
 * The desk-nook's R3F canvas, split into its own chunk so `PlattDeskWidget` can `React.lazy`
 * it in behind Suspense (per the desk-widget task: keep 3D off the initial bundle, degrade to
 * the 2D fallback for reduced-motion / no-WebGL / a lost context).
 */
export default function DeskScene3D({
  state,
  speech,
  onContextLost,
}: {
  state: ThreeStageState;
  speech: string;
  onContextLost: () => void;
}) {
  const setState = usePlattSceneStore((s) => s.setState);
  const setSpeech = usePlattSceneStore((s) => s.setSpeech);

  React.useEffect(() => setState(state), [state, setState]);
  React.useEffect(() => setSpeech(speech), [speech, setSpeech]);

  return (
    <Canvas
      aria-hidden="true"
      camera={{ fov: DESK_CAMERA_DEFAULT.fov, position: DESK_CAMERA_DEFAULT.position }}
      dpr={[1, 1.5]}
      gl={{ antialias: true, powerPreference: "low-power" }}
    >
      <DeskContextLossGuard onContextLost={onContextLost} />
      <DeskWorld state={state} />
    </Canvas>
  );
}
