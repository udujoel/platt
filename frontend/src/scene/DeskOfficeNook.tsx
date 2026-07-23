import React from "react";
import { useFrame } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei";
import { DoubleSide, type Mesh } from "three";
import { usePlattSceneStore } from "./scene-store";

/** Small floor pad under the desk/chair; ContactShadows (drei) grounds the character, no shadow maps. */
function Floor() {
  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[2.6, 2]} />
        <meshStandardMaterial color="#161d28" roughness={0.92} />
      </mesh>
      <ContactShadows position={[0, 0.002, 0]} opacity={0.5} scale={2.4} blur={2} far={1.4} resolution={256} color="#05070b" />
    </>
  );
}

/** Cropped back wall + a bright window-hint panel, read as a half-cut corner of a room. */
function PartialWall() {
  return (
    <>
      <mesh position={[-0.15, 1.15, -0.92]}>
        <boxGeometry args={[2.3, 2.3, 0.08]} />
        <meshStandardMaterial color="#1b2330" roughness={0.95} />
      </mesh>
      {/* Warm window hint: a soft emissive pane peeking in from the cropped edge. */}
      <mesh position={[0.85, 1.55, -0.87]}>
        <planeGeometry args={[0.5, 0.62]} />
        <meshStandardMaterial color="#3a3120" emissive="#ffb454" emissiveIntensity={0.35} roughness={0.7} />
      </mesh>
    </>
  );
}

/** Small desk lamp: base + shade mesh plus the actual warm point light that grounds the nook's mood. */
function DeskLamp() {
  return (
    <group position={[0.62, 0.66, -0.55]}>
      <mesh position={[0, -0.05, 0]}>
        <cylinderGeometry args={[0.05, 0.06, 0.02, 10]} />
        <meshStandardMaterial color="#2b2f38" roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.1, 0]}>
        <cylinderGeometry args={[0.012, 0.012, 0.3, 6]} />
        <meshStandardMaterial color="#2b2f38" roughness={0.6} />
      </mesh>
      <mesh position={[0, 0.27, 0]} rotation={[Math.PI, 0, 0]}>
        <coneGeometry args={[0.09, 0.12, 12, 1, true]} />
        <meshStandardMaterial color="#ffb454" emissive="#ffb454" emissiveIntensity={0.9} roughness={0.4} side={DoubleSide} />
      </mesh>
      <pointLight position={[0, 0.24, 0]} color="#ffb454" intensity={3.2} distance={1.5} decay={2} />
    </group>
  );
}

/** Compact single-person desk; monitor emissive tracks the shared scene state, same convention as Office.tsx. */
function DeskAndMonitor() {
  const state = usePlattSceneStore((s) => s.state);
  const monitorColor = state === "concerned" ? "#f87171" : state === "working" || state === "thinking" ? "#ffb454" : "#2dd4bf";

  return (
    <group position={[0.15, 0, -0.55]}>
      <mesh position={[0, 0.6, 0]}>
        <boxGeometry args={[1.3, 0.08, 0.55]} />
        <meshStandardMaterial color="#9d6037" roughness={0.74} />
      </mesh>
      <mesh position={[-0.55, 0.28, 0.2]}>
        <boxGeometry args={[0.07, 0.56, 0.07]} />
        <meshStandardMaterial color="#4a3722" roughness={0.8} />
      </mesh>
      <mesh position={[0.55, 0.28, 0.2]}>
        <boxGeometry args={[0.07, 0.56, 0.07]} />
        <meshStandardMaterial color="#4a3722" roughness={0.8} />
      </mesh>
      <mesh position={[-0.1, 0.98, -0.15]}>
        <boxGeometry args={[0.46, 0.42, 0.05]} />
        <meshStandardMaterial color="#222936" metalness={0.32} roughness={0.55} />
      </mesh>
      <mesh position={[-0.1, 0.98, -0.12]}>
        <planeGeometry args={[0.36, 0.3]} />
        <meshStandardMaterial color={monitorColor} emissive={monitorColor} emissiveIntensity={state === "working" ? 1.4 : 0.7} />
      </mesh>
      <mesh position={[-0.1, 0.66, -0.14]}>
        <boxGeometry args={[0.32, 0.05, 0.14]} />
        <meshStandardMaterial color="#384150" />
      </mesh>
    </group>
  );
}

/** Small desk chair: seat + backrest, positioned so its seat height reads under the character's hips. */
function Chair() {
  return (
    <group position={[0.05, 0, -0.05]}>
      <mesh position={[0, 0.42, 0]}>
        <boxGeometry args={[0.42, 0.06, 0.4]} />
        <meshStandardMaterial color="#2f3742" roughness={0.7} />
      </mesh>
      <mesh position={[0, 0.68, -0.19]}>
        <boxGeometry args={[0.4, 0.5, 0.06]} />
        <meshStandardMaterial color="#2f3742" roughness={0.7} />
      </mesh>
      <mesh position={[0, 0.2, 0]}>
        <cylinderGeometry args={[0.03, 0.05, 0.36, 8]} />
        <meshStandardMaterial color="#1b2027" metalness={0.4} roughness={0.5} />
      </mesh>
    </group>
  );
}

/** Small emissive tick that pulses faintly on the desk to keep the corner reading as "alive" at rest. */
function DeskStatusTick() {
  const ref = React.useRef<Mesh>(null);
  const state = usePlattSceneStore((s) => s.state);
  const color = state === "concerned" ? "#f87171" : "#2dd4bf";

  useFrame(({ clock }) => {
    if (!ref.current) return;
    const material = ref.current.material as unknown as { emissiveIntensity: number };
    material.emissiveIntensity = 0.5 + Math.abs(Math.sin(clock.getElapsedTime() * 1.8)) * 0.8;
  });

  return (
    <mesh ref={ref} position={[0.72, 0.63, -0.32]}>
      <boxGeometry args={[0.05, 0.03, 0.02]} />
      <meshStandardMaterial color={color} emissive={color} emissiveIntensity={0.6} />
    </mesh>
  );
}

/** The half-cut desk nook: floor, partial wall/window hint, lamp, desk + monitor, chair. Per the desk-widget task. */
export function DeskOfficeNook() {
  return (
    <>
      <Floor />
      <PartialWall />
      <DeskLamp />
      <DeskAndMonitor />
      <Chair />
      <DeskStatusTick />
    </>
  );
}
