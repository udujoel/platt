import React from "react";
import { useFrame } from "@react-three/fiber";
import { MathUtils, type Group, type Mesh } from "three";
import { getThreeStagePose } from "../three-stage-pose";
import { amplitudeToJawRotation } from "../voice/amplitude-jaw";
import type { CharacterHandle, PlattCharacterProps } from "./types";

const BREATH_AMPLITUDE = 0.012;
const BREATH_HZ = 1.4;

/**
 * Procedural box-and-capsule rig behind the `CharacterHandle` interface. Used as the runtime
 * fallback when `platt.glb` (T-D1, see `ASSETS.md`) is missing or fails to load — see
 * `PlattCharacter.tsx`. Rounded joint spheres, a soft floor-contact shadow blob, and a subtle
 * idle breathing bob are purely cosmetic (they read the same pose/anchor/facing/jaw signals as
 * the glb rig) so this stays a drop-in visual stand-in, not a second source of behavior.
 */
export const ProceduralPlatt = React.forwardRef<CharacterHandle, PlattCharacterProps>(function ProceduralPlatt(
  { state, clip, anchor, facing },
  ref,
) {
  const rig = React.useRef<Group>(null);
  const head = React.useRef<Group>(null);
  const jaw = React.useRef<Mesh>(null);
  const leftArm = React.useRef<Mesh>(null);
  const rightArm = React.useRef<Mesh>(null);
  const breathGroup = React.useRef<Group>(null);
  const currentClip = React.useRef(clip);
  const jawAmplitude = React.useRef(0);

  React.useEffect(() => {
    currentClip.current = clip;
  }, [clip]);

  React.useImperativeHandle(
    ref,
    () => ({
      get currentClip() {
        return currentClip.current;
      },
      playClip: (plan) => {
        currentClip.current = plan.fadeInClip;
      },
      setJawAmplitude: (amplitude) => {
        jawAmplitude.current = amplitude;
      },
    }),
    [],
  );

  useFrame(({ clock }, delta) => {
    const elapsed = clock.getElapsedTime();
    const pose = getThreeStagePose(state, elapsed);
    const targetX = anchor ? anchor.current[0] : pose.x;
    const targetZ = anchor ? anchor.current[2] : 0;
    if (rig.current) {
      rig.current.position.x = MathUtils.damp(rig.current.position.x, targetX, 4, delta);
      rig.current.position.z = MathUtils.damp(rig.current.position.z, targetZ, 4, delta);
      rig.current.position.y = MathUtils.damp(rig.current.position.y, pose.y, 8, delta);
      rig.current.rotation.z = MathUtils.damp(rig.current.rotation.z, pose.bodyLean, 10, delta);
      if (facing) {
        rig.current.rotation.y = MathUtils.damp(rig.current.rotation.y, facing.current, 6, delta);
      }
    }
    if (head.current) head.current.rotation.z = MathUtils.damp(head.current.rotation.z, pose.headTilt, 8, delta);
    if (jaw.current) {
      jaw.current.rotation.x = MathUtils.damp(jaw.current.rotation.x, amplitudeToJawRotation(jawAmplitude.current), 20, delta);
    }
    if (leftArm.current) leftArm.current.rotation.z = MathUtils.damp(leftArm.current.rotation.z, pose.leftArm, 12, delta);
    if (rightArm.current) rightArm.current.rotation.z = MathUtils.damp(rightArm.current.rotation.z, pose.rightArm, 12, delta);
    if (breathGroup.current) {
      breathGroup.current.scale.y = 1 + Math.sin(elapsed * BREATH_HZ * Math.PI * 2) * BREATH_AMPLITUDE;
    }
  });

  return (
    <group ref={rig} position={[0, 1.05, 0]}>
      {/* Soft contact-shadow blob grounds the rig against the floor instead of it looking like it's floating. */}
      <mesh position={[0, -0.985, 0]} rotation-x={-Math.PI / 2}>
        <circleGeometry args={[0.36, 20]} />
        <meshBasicMaterial color="#0a0e14" transparent opacity={0.22} depthWrite={false} />
      </mesh>

      <group ref={breathGroup} position={[0, 0.28, 0]}>
        <group ref={head} position={[0, 0.65, 0]}>
          <mesh castShadow>
            <sphereGeometry args={[0.37, 20, 16]} />
            <meshStandardMaterial color="#d99a70" roughness={0.62} />
          </mesh>
          <mesh position={[0, 0.24, 0.11]} castShadow>
            <boxGeometry args={[0.48, 0.13, 0.21]} />
            <meshStandardMaterial color="#263145" roughness={0.4} metalness={0.15} />
          </mesh>
          <mesh ref={jaw} position={[0, 0.08, 0.17]} castShadow>
            <boxGeometry args={[0.17, 0.08, 0.09]} />
            <meshStandardMaterial color="#96613f" roughness={0.7} />
          </mesh>
        </group>
        {/* Neck sphere fills the head/torso gap so the head reads as attached, not stacked. */}
        <mesh position={[0, 0.34, 0]} castShadow>
          <sphereGeometry args={[0.14, 12, 10]} />
          <meshStandardMaterial color="#c98c64" roughness={0.65} />
        </mesh>

        <mesh castShadow>
          <boxGeometry args={[0.66, 0.85, 0.36]} />
          <meshStandardMaterial color="#304969" roughness={0.55} metalness={0.08} />
        </mesh>
        <mesh position={[0, 0.06, 0.2]}>
          <boxGeometry args={[0.21, 0.5, 0.03]} />
          <meshStandardMaterial color="#e5edf0" roughness={0.35} />
        </mesh>

        {/* Rounded shoulder joints hide the flat capsule caps and give the silhouette softer edges. */}
        <mesh position={[-0.25, 0.32, 0]} castShadow>
          <sphereGeometry args={[0.135, 12, 10]} />
          <meshStandardMaterial color="#304969" roughness={0.55} />
        </mesh>
        <mesh position={[0.25, 0.32, 0]} castShadow>
          <sphereGeometry args={[0.135, 12, 10]} />
          <meshStandardMaterial color="#304969" roughness={0.55} />
        </mesh>
        <mesh ref={leftArm} position={[-0.25, 0.16, 0]} castShadow>
          <capsuleGeometry args={[0.1, 0.5, 6, 10]} />
          <meshStandardMaterial color="#304969" roughness={0.58} />
          <mesh position={[0, -0.29, 0]} castShadow>
            <sphereGeometry args={[0.1, 10, 8]} />
            <meshStandardMaterial color="#d99a70" roughness={0.62} />
          </mesh>
        </mesh>
        <mesh ref={rightArm} position={[0.25, 0.16, 0]} castShadow>
          <capsuleGeometry args={[0.1, 0.5, 6, 10]} />
          <meshStandardMaterial color="#304969" roughness={0.58} />
          <mesh position={[0, -0.29, 0]} castShadow>
            <sphereGeometry args={[0.1, 10, 8]} />
            <meshStandardMaterial color="#d99a70" roughness={0.62} />
          </mesh>
        </mesh>
      </group>

      {/* Hip joints */}
      <mesh position={[-0.19, -0.28, 0]} castShadow>
        <sphereGeometry args={[0.12, 12, 10]} />
        <meshStandardMaterial color="#263d5b" roughness={0.6} />
      </mesh>
      <mesh position={[0.19, -0.28, 0]} castShadow>
        <sphereGeometry args={[0.12, 12, 10]} />
        <meshStandardMaterial color="#263d5b" roughness={0.6} />
      </mesh>
      <mesh position={[-0.19, -0.55, 0]} castShadow>
        <capsuleGeometry args={[0.11, 0.42, 6, 10]} />
        <meshStandardMaterial color="#263d5b" roughness={0.6} />
      </mesh>
      <mesh position={[0.19, -0.55, 0]} castShadow>
        <capsuleGeometry args={[0.11, 0.42, 6, 10]} />
        <meshStandardMaterial color="#263d5b" roughness={0.6} />
      </mesh>
      {/* Knee joints round out the leg silhouette where shin meets thigh. */}
      <mesh position={[-0.19, -0.78, 0]} castShadow>
        <sphereGeometry args={[0.1, 10, 8]} />
        <meshStandardMaterial color="#1f3350" roughness={0.6} />
      </mesh>
      <mesh position={[0.19, -0.78, 0]} castShadow>
        <sphereGeometry args={[0.1, 10, 8]} />
        <meshStandardMaterial color="#1f3350" roughness={0.6} />
      </mesh>
      <mesh position={[-0.19, -0.92, 0.06]} castShadow>
        <boxGeometry args={[0.28, 0.11, 0.4]} />
        <meshStandardMaterial color="#161c26" roughness={0.5} metalness={0.1} />
      </mesh>
      <mesh position={[0.19, -0.92, 0.06]} castShadow>
        <boxGeometry args={[0.28, 0.11, 0.4]} />
        <meshStandardMaterial color="#161c26" roughness={0.5} metalness={0.1} />
      </mesh>
    </group>
  );
});
