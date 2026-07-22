import React from "react";
import { useFrame } from "@react-three/fiber";
import { CanvasTexture, RepeatWrapping, type Mesh } from "three";
import { ContactShadows } from "@react-three/drei";
import { usePlattSceneStore } from "./scene-store";
import { isPebbleKickComplete, pebbleArcPosition, PEBBLE_ORIGIN, PEBBLE_TARGET } from "./pebble-kick";

/** Small procedural carpet-grid texture so the floor reads as a warm low-poly surface, not a flat fill. */
function useFloorTexture() {
  return React.useMemo(() => {
    const size = 128;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#161d28";
    ctx.fillRect(0, 0, size, size);
    ctx.strokeStyle = "rgba(255, 180, 84, 0.05)";
    ctx.lineWidth = 1;
    ctx.strokeRect(0.5, 0.5, size - 1, size - 1);
    const texture = new CanvasTexture(canvas);
    texture.wrapS = RepeatWrapping;
    texture.wrapT = RepeatWrapping;
    texture.repeat.set(10, 8);
    return texture;
  }, []);
}

/** Floor plane: subtle carpet-grid texture, ContactShadows (drei) instead of real-time shadow maps per PRD 5.2/5.4. */
function Floor() {
  const texture = useFloorTexture();
  return (
    <>
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[12, 10]} />
        <meshStandardMaterial color="#161d28" map={texture ?? undefined} roughness={0.92} />
      </mesh>
      <ContactShadows position={[0, 0.002, 0]} opacity={0.55} scale={12} blur={2.2} far={3} resolution={512} color="#05070b" />
    </>
  );
}

function Desk() {
  return (
    <mesh position={[1.45, 0.76, -0.45]}>
      <boxGeometry args={[3.2, 0.22, 1.15]} />
      <meshStandardMaterial color="#9d6037" roughness={0.74} />
    </mesh>
  );
}

/** Monitor emissive is driven by store state per PRD 5.2 (bright in working, red tint in concerned). */
function Monitor() {
  const state = usePlattSceneStore((s) => s.state);
  const monitorColor = state === "concerned" ? "#f87171" : state === "working" || state === "thinking" ? "#ffb454" : "#2dd4bf";
  return (
    <>
      <mesh position={[1.45, 1.66, -0.43]}>
        <boxGeometry args={[1.05, 1.05, 0.12]} />
        <meshStandardMaterial color="#222936" metalness={0.32} roughness={0.55} />
      </mesh>
      <mesh position={[1.45, 1.66, -0.35]}>
        <planeGeometry args={[0.82, 0.78]} />
        <meshStandardMaterial color={monitorColor} emissive={monitorColor} emissiveIntensity={state === "working" ? 1.45 : 0.72} />
      </mesh>
      <mesh position={[1.45, 0.99, -0.33]}>
        <boxGeometry args={[1.05, 0.08, 0.42]} />
        <meshStandardMaterial color="#384150" />
      </mesh>
    </>
  );
}

const BOARD_COLUMN_CAP = 6;
const BOARD_COLUMN_COLORS = ["#8ea0b8", "#ffb454", "#2dd4bf"] as const;
const BOARD_COLUMN_X = [-0.55, 0, 0.55] as const;

function BoardColumn({ x, count, color }: { x: number; count: number; color: string }) {
  const clamped = Math.max(0, Math.min(count, BOARD_COLUMN_CAP));
  return (
    <group position={[x, 0, 0]}>
      {Array.from({ length: clamped }, (_, i) => (
        <mesh key={i} position={[0, 0.08 + i * 0.11, 0]}>
          <boxGeometry args={[0.32, 0.09, 0.03]} />
          <meshStandardMaterial color={color} />
        </mesh>
      ))}
    </group>
  );
}

/** Wall board column counts are fed from the Kanban store per PRD 5.2. */
function Board() {
  const columns = usePlattSceneStore((s) => s.boardColumns);
  return (
    <group position={[-2.6, 2.2, -2.02]}>
      <mesh>
        <boxGeometry args={[1.8, 1.05, 0.14]} />
        <meshStandardMaterial color="#e9d8b6" />
      </mesh>
      <group position={[0, -0.4, 0.09]}>
        {BOARD_COLUMN_X.map((x, i) => (
          <BoardColumn key={i} x={x} count={columns[i]} color={BOARD_COLUMN_COLORS[i]} />
        ))}
      </group>
    </group>
  );
}

const RACK_LIGHT_ROWS = [0.75, 1.05, 1.35, 1.65];
const RACK_LIGHT_COLORS = ["#2dd4bf", "#ffb454", "#2dd4bf", "#f87171"] as const;

/** A row of small emissive strips that blink at their own offset phase, per PRD 5.2 ("blinking lights"). */
function ServerRackLights() {
  const refs = React.useRef<Array<Mesh | null>>([]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    refs.current.forEach((mesh, i) => {
      if (!mesh) return;
      const material = mesh.material as unknown as { emissiveIntensity: number };
      material.emissiveIntensity = 0.4 + Math.abs(Math.sin(t * (1.6 + i * 0.7) + i)) * 1.1;
    });
  });

  return (
    <>
      {RACK_LIGHT_ROWS.map((y, i) => (
        <mesh key={y} ref={(el) => { refs.current[i] = el; }} position={[2.75, y, -1.57]}>
          <boxGeometry args={[0.7, 0.05, 0.02]} />
          <meshStandardMaterial color={RACK_LIGHT_COLORS[i]} emissive={RACK_LIGHT_COLORS[i]} emissiveIntensity={0.6} />
        </mesh>
      ))}
    </>
  );
}

function ServerRack() {
  return (
    <>
      <mesh position={[2.75, 1.25, -1.85]}>
        <boxGeometry args={[1.08, 2.3, 0.55]} />
        <meshStandardMaterial color="#111720" metalness={0.4} roughness={0.55} />
      </mesh>
      <ServerRackLights />
    </>
  );
}

function Plant() {
  return (
    <>
      <mesh position={[-3.25, 0.55, -0.65]}>
        <cylinderGeometry args={[0.36, 0.48, 0.75, 10]} />
        <meshStandardMaterial color="#bb7449" />
      </mesh>
      <mesh position={[-3.25, 1.25, -0.65]}>
        <coneGeometry args={[0.7, 1.55, 9]} />
        <meshStandardMaterial color="#2f8c6a" roughness={0.8} />
      </mesh>
    </>
  );
}

/** Small sphere that runs the scripted kick arc (scene/pebble-kick.ts) when triggered by the controller. */
function Pebble() {
  const ref = React.useRef<Mesh>(null);
  const pebbleKickAt = usePlattSceneStore((s) => s.pebbleKickAt);

  useFrame(({ clock }) => {
    if (!ref.current) return;
    if (pebbleKickAt === null) {
      ref.current.position.set(...PEBBLE_ORIGIN);
      return;
    }
    const elapsed = clock.getElapsedTime() - pebbleKickAt;
    const [x, y, z] = isPebbleKickComplete(elapsed) ? PEBBLE_TARGET : pebbleArcPosition(PEBBLE_ORIGIN, PEBBLE_TARGET, elapsed);
    ref.current.position.set(x, y, z);
  });

  return (
    <mesh ref={ref} position={PEBBLE_ORIGIN}>
      <dodecahedronGeometry args={[0.17, 0]} />
      <meshStandardMaterial color="#aeb7b7" roughness={0.94} />
    </mesh>
  );
}

/** The diorama: desk, monitor, wall board, server rack, plant, floor, pebble. Per PRD 5.2. */
export function Office() {
  return (
    <>
      <Floor />
      <Desk />
      <Monitor />
      <Board />
      <ServerRack />
      <Plant />
      <Pebble />
    </>
  );
}
