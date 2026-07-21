import React from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { createWebGLContextLossHandler } from "../stage-renderer";
import type { ThreeStageState } from "../three-stage-pose";
import { usePlattSceneStore, type BoardColumns } from "./scene-store";
import { Office } from "./Office";
import { PlattController } from "./PlattController";
import { CameraRig } from "./CameraRig";
import { Bubble } from "./Bubble";

function WebGLContextLossGuard({ onContextLost }: { onContextLost: () => void }) {
  const gl = useThree((state) => state.gl);

  React.useEffect(() => {
    const canvas = gl.domElement;
    const handleContextLoss = createWebGLContextLossHandler(onContextLost);
    canvas.addEventListener("webglcontextlost", handleContextLoss);
    return () => canvas.removeEventListener("webglcontextlost", handleContextLoss);
  }, [gl, onContextLost]);

  return null;
}

function ThreeOfficeWorld({ state }: { state: ThreeStageState }) {
  return (
    <>
      <color attach="background" args={["#111720"]} />
      <fog attach="fog" args={["#111720", 7, 14]} />
      <ambientLight intensity={1.15} />
      <directionalLight position={[3, 6, 5]} intensity={2.4} castShadow />
      <pointLight
        position={[1.45, 2, 0.8]}
        color={state === "concerned" ? "#f87171" : "#ffb454"}
        intensity={state === "working" ? 16 : 7}
        distance={4.2}
      />
      <Office />
      <PlattController />
      <CameraRig />
    </>
  );
}

export function ThreeOfficeScene({
  state,
  speech,
  onContextLost,
  boardColumns,
}: {
  state: ThreeStageState;
  speech: string;
  onContextLost: () => void;
  boardColumns?: BoardColumns;
}) {
  const setState = usePlattSceneStore((s) => s.setState);
  const setSpeech = usePlattSceneStore((s) => s.setSpeech);
  const setBoardColumns = usePlattSceneStore((s) => s.setBoardColumns);

  React.useEffect(() => setState(state), [state, setState]);
  React.useEffect(() => setSpeech(speech), [speech, setSpeech]);
  React.useEffect(() => {
    setBoardColumns(boardColumns ?? [0, 0, 0]);
  }, [boardColumns, setBoardColumns]);

  return (
    <div className="threeOfficeScene">
      <Canvas
        aria-hidden="true"
        camera={{ fov: 42, position: [0, 3.15, 7.6] }}
        dpr={[1, 1.5]}
        gl={{ antialias: true, powerPreference: "low-power" }}
        shadows
      >
        <WebGLContextLossGuard onContextLost={onContextLost} />
        <ThreeOfficeWorld state={state} />
      </Canvas>
      <Bubble />
    </div>
  );
}
