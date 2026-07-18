import React from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { MathUtils, type Group, type Mesh } from "three";
import { getThreeStagePose } from "./three-stage-pose";
import type { ThreeStageState } from "./three-stage-pose";

function PlattRig({ state }: { state: ThreeStageState }) {
  const rig = React.useRef<Group>(null);
  const head = React.useRef<Mesh>(null);
  const leftArm = React.useRef<Mesh>(null);
  const rightArm = React.useRef<Mesh>(null);

  useFrame(({ clock }, delta) => {
    const pose = getThreeStagePose(state, clock.getElapsedTime());
    if (rig.current) {
      rig.current.position.x = MathUtils.damp(rig.current.position.x, pose.x, 4, delta);
      rig.current.position.y = MathUtils.damp(rig.current.position.y, pose.y, 8, delta);
      rig.current.rotation.z = MathUtils.damp(rig.current.rotation.z, pose.bodyLean, 10, delta);
    }
    if (head.current) head.current.rotation.z = MathUtils.damp(head.current.rotation.z, pose.headTilt, 8, delta);
    if (leftArm.current) leftArm.current.rotation.z = MathUtils.damp(leftArm.current.rotation.z, pose.leftArm, 12, delta);
    if (rightArm.current) rightArm.current.rotation.z = MathUtils.damp(rightArm.current.rotation.z, pose.rightArm, 12, delta);
  });

  return (
    <group ref={rig} position={[0, 1.05, 0]}>
      <mesh ref={head} position={[0, 0.93, 0]} castShadow><sphereGeometry args={[0.39, 18, 14]} /><meshStandardMaterial color="#c98c64" roughness={0.7} /></mesh>
      <mesh position={[0, 1.18, 0.12]} castShadow><boxGeometry args={[0.5, 0.14, 0.22]} /><meshStandardMaterial color="#263145" roughness={0.82} /></mesh>
      <mesh position={[0, 0.28, 0]} castShadow><boxGeometry args={[0.7, 0.95, 0.38]} /><meshStandardMaterial color="#304969" roughness={0.78} /></mesh>
      <mesh position={[0, 0.38, 0.21]}><boxGeometry args={[0.23, 0.58, 0.03]} /><meshStandardMaterial color="#e5edf0" /></mesh>
      <mesh ref={leftArm} position={[-0.24, 0.48, 0]} castShadow><capsuleGeometry args={[0.11, 0.62, 6, 10]} /><meshStandardMaterial color="#304969" /></mesh>
      <mesh ref={rightArm} position={[0.24, 0.48, 0]} castShadow><capsuleGeometry args={[0.11, 0.62, 6, 10]} /><meshStandardMaterial color="#304969" /></mesh>
      <mesh position={[-0.2, -0.54, 0]} castShadow><boxGeometry args={[0.2, 0.55, 0.23]} /><meshStandardMaterial color="#263d5b" /></mesh>
      <mesh position={[0.2, -0.54, 0]} castShadow><boxGeometry args={[0.2, 0.55, 0.23]} /><meshStandardMaterial color="#263d5b" /></mesh>
      <mesh position={[-0.2, -0.84, 0.08]} castShadow><boxGeometry args={[0.3, 0.12, 0.42]} /><meshStandardMaterial color="#19202c" /></mesh>
      <mesh position={[0.2, -0.84, 0.08]} castShadow><boxGeometry args={[0.3, 0.12, 0.42]} /><meshStandardMaterial color="#19202c" /></mesh>
    </group>
  );
}

function OfficeProps({ state }: { state: ThreeStageState }) {
  const monitorColor = state === "concerned" ? "#f87171" : state === "working" || state === "thinking" ? "#ffb454" : "#2dd4bf";

  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow><planeGeometry args={[12, 10]} /><meshStandardMaterial color="#161d28" roughness={0.9} /></mesh>
      <mesh position={[0, 2.85, -2.2]} receiveShadow><boxGeometry args={[8.6, 4.8, 0.2]} /><meshStandardMaterial color="#202735" roughness={0.94} /></mesh>
      <mesh position={[-2.6, 2.2, -2.02]} castShadow><boxGeometry args={[1.8, 1.05, 0.14]} /><meshStandardMaterial color="#e9d8b6" /></mesh>
      <mesh position={[2.75, 1.25, -1.85]} castShadow><boxGeometry args={[1.08, 2.3, 0.55]} /><meshStandardMaterial color="#111720" metalness={0.4} roughness={0.55} /></mesh>
      <mesh position={[1.45, 0.76, -0.45]} castShadow><boxGeometry args={[3.2, 0.22, 1.15]} /><meshStandardMaterial color="#9d6037" roughness={0.74} /></mesh>
      <mesh position={[1.45, 1.66, -0.43]} castShadow><boxGeometry args={[1.05, 1.05, 0.12]} /><meshStandardMaterial color="#222936" metalness={0.32} roughness={0.55} /></mesh>
      <mesh position={[1.45, 1.66, -0.35]}><planeGeometry args={[0.82, 0.78]} /><meshStandardMaterial color={monitorColor} emissive={monitorColor} emissiveIntensity={state === "working" ? 1.45 : 0.72} /></mesh>
      <mesh position={[1.45, 0.99, -0.33]} castShadow><boxGeometry args={[1.05, 0.08, 0.42]} /><meshStandardMaterial color="#384150" /></mesh>
      <mesh position={[-3.25, 0.55, -0.65]} castShadow><cylinderGeometry args={[0.36, 0.48, 0.75, 10]} /><meshStandardMaterial color="#bb7449" /></mesh>
      <mesh position={[-3.25, 1.25, -0.65]} castShadow><coneGeometry args={[0.7, 1.55, 9]} /><meshStandardMaterial color="#2f8c6a" roughness={0.8} /></mesh>
      <mesh position={[-0.25, 0.18, 0.5]} castShadow><dodecahedronGeometry args={[0.17, 0]} /><meshStandardMaterial color="#aeb7b7" roughness={0.94} /></mesh>
    </>
  );
}

function ThreeOfficeWorld({ state }: { state: ThreeStageState }) {
  return (
    <>
      <color attach="background" args={["#111720"]} />
      <fog attach="fog" args={["#111720", 7, 14]} />
      <ambientLight intensity={1.15} />
      <directionalLight position={[3, 6, 5]} intensity={2.4} castShadow />
      <pointLight position={[1.45, 2, 0.8]} color={state === "concerned" ? "#f87171" : "#ffb454"} intensity={state === "working" ? 16 : 7} distance={4.2} />
      <OfficeProps state={state} />
      <PlattRig state={state} />
    </>
  );
}

export function ThreeOfficeScene({ state, speech }: { state: ThreeStageState; speech: string }) {
  return (
    <div className="threeOfficeScene">
      <Canvas aria-hidden="true" camera={{ fov: 42, position: [0, 3.15, 7.6] }} dpr={[1, 1.5]} gl={{ antialias: true, powerPreference: "low-power" }} shadows>
        <ThreeOfficeWorld state={state} />
      </Canvas>
      {state === "talking" && speech ? <div className="threeSpeechBubble" role="status" aria-live="polite" aria-atomic="true">{speech.slice(-180)}</div> : null}
    </div>
  );
}
