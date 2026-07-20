import React from "react";
import { useFrame } from "@react-three/fiber";
import { MathUtils, type Group, type Mesh } from "three";
import { getThreeStagePose } from "../three-stage-pose";
import type { CharacterHandle, PlattCharacterProps } from "./types";

/**
 * Renders the procedural box rig behind the `CharacterHandle` interface. When `platt.glb`
 * (T-D1) is ready, this component's body swaps to `useGLTF` + `useAnimations` while keeping
 * the same props/ref contract, so `PlattController` needs no changes.
 */
export const PlattCharacter = React.forwardRef<CharacterHandle, PlattCharacterProps>(function PlattCharacter(
  { state, clip, anchor },
  ref,
) {
  const rig = React.useRef<Group>(null);
  const head = React.useRef<Group>(null);
  const leftArm = React.useRef<Mesh>(null);
  const rightArm = React.useRef<Mesh>(null);
  const currentClip = React.useRef(clip);

  React.useEffect(() => {
    currentClip.current = clip;
  }, [clip]);

  React.useImperativeHandle(
    ref,
    () => ({
      get currentClip() {
        return currentClip.current;
      },
      playClip: (next) => {
        currentClip.current = next;
      },
    }),
    [],
  );

  useFrame(({ clock }, delta) => {
    const pose = getThreeStagePose(state, clock.getElapsedTime());
    const targetX = anchor ? anchor.current[0] : pose.x;
    const targetZ = anchor ? anchor.current[2] : 0;
    if (rig.current) {
      rig.current.position.x = MathUtils.damp(rig.current.position.x, targetX, 4, delta);
      rig.current.position.z = MathUtils.damp(rig.current.position.z, targetZ, 4, delta);
      rig.current.position.y = MathUtils.damp(rig.current.position.y, pose.y, 8, delta);
      rig.current.rotation.z = MathUtils.damp(rig.current.rotation.z, pose.bodyLean, 10, delta);
    }
    if (head.current) head.current.rotation.z = MathUtils.damp(head.current.rotation.z, pose.headTilt, 8, delta);
    if (leftArm.current) leftArm.current.rotation.z = MathUtils.damp(leftArm.current.rotation.z, pose.leftArm, 12, delta);
    if (rightArm.current) rightArm.current.rotation.z = MathUtils.damp(rightArm.current.rotation.z, pose.rightArm, 12, delta);
  });

  return (
    <group ref={rig} position={[0, 1.05, 0]}>
      <group ref={head} position={[0, 0.93, 0]}>
        <mesh castShadow>
          <sphereGeometry args={[0.39, 18, 14]} />
          <meshStandardMaterial color="#c98c64" roughness={0.7} />
        </mesh>
        <mesh position={[0, 0.25, 0.12]} castShadow>
          <boxGeometry args={[0.5, 0.14, 0.22]} />
          <meshStandardMaterial color="#263145" roughness={0.82} />
        </mesh>
      </group>
      <mesh position={[0, 0.28, 0]} castShadow>
        <boxGeometry args={[0.7, 0.95, 0.38]} />
        <meshStandardMaterial color="#304969" roughness={0.78} />
      </mesh>
      <mesh position={[0, 0.38, 0.21]}>
        <boxGeometry args={[0.23, 0.58, 0.03]} />
        <meshStandardMaterial color="#e5edf0" />
      </mesh>
      <mesh ref={leftArm} position={[-0.24, 0.48, 0]} castShadow>
        <capsuleGeometry args={[0.11, 0.62, 6, 10]} />
        <meshStandardMaterial color="#304969" />
      </mesh>
      <mesh ref={rightArm} position={[0.24, 0.48, 0]} castShadow>
        <capsuleGeometry args={[0.11, 0.62, 6, 10]} />
        <meshStandardMaterial color="#304969" />
      </mesh>
      <mesh position={[-0.2, -0.54, 0]} castShadow>
        <boxGeometry args={[0.2, 0.55, 0.23]} />
        <meshStandardMaterial color="#263d5b" />
      </mesh>
      <mesh position={[0.2, -0.54, 0]} castShadow>
        <boxGeometry args={[0.2, 0.55, 0.23]} />
        <meshStandardMaterial color="#263d5b" />
      </mesh>
      <mesh position={[-0.2, -0.84, 0.08]} castShadow>
        <boxGeometry args={[0.3, 0.12, 0.42]} />
        <meshStandardMaterial color="#19202c" />
      </mesh>
      <mesh position={[0.2, -0.84, 0.08]} castShadow>
        <boxGeometry args={[0.3, 0.12, 0.42]} />
        <meshStandardMaterial color="#19202c" />
      </mesh>
    </group>
  );
});
