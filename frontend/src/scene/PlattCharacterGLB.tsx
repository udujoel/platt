import React from "react";
import { useFrame } from "@react-three/fiber";
import { useAnimations, useGLTF } from "@react-three/drei";
import { MathUtils, type Group } from "three";
import { getThreeStagePose } from "../three-stage-pose";
import { applyCrossfadePlan } from "./glb-character-actions";
import type { CharacterHandle, PlattCharacterProps } from "./types";

export const PLATT_GLB_PATH = "/platt.glb";

/**
 * glb-driven character (T-D1): loads `platt.glb` (see `ASSETS.md`) via drei's `useGLTF` and
 * drives its Mixamo clips through `useAnimations`, behind the same `CharacterHandle` contract
 * as `ProceduralPlatt`. `useGLTF` suspends while loading and throws on failure — both are
 * handled by the `Suspense`/`CharacterErrorBoundary` pair in `PlattCharacter.tsx`, not here.
 */
export const PlattCharacterGLB = React.forwardRef<CharacterHandle, PlattCharacterProps>(function PlattCharacterGLB(
  { state, clip, anchor },
  ref,
) {
  const rig = React.useRef<Group>(null);
  const { scene, animations } = useGLTF(PLATT_GLB_PATH);
  const { actions } = useAnimations(animations, rig);
  const currentClip = React.useRef(clip);
  const startedInitialClip = React.useRef(false);

  React.useEffect(() => {
    if (startedInitialClip.current) return;
    startedInitialClip.current = true;
    actions[clip]?.reset().fadeIn(0).play();
  }, [actions, clip]);

  React.useImperativeHandle(
    ref,
    () => ({
      get currentClip() {
        return currentClip.current;
      },
      playClip: (plan) => {
        currentClip.current = applyCrossfadePlan(actions, plan);
      },
    }),
    [actions],
  );

  useFrame(({ clock }, delta) => {
    const pose = getThreeStagePose(state, clock.getElapsedTime());
    const targetX = anchor ? anchor.current[0] : pose.x;
    const targetZ = anchor ? anchor.current[2] : 0;
    if (rig.current) {
      rig.current.position.x = MathUtils.damp(rig.current.position.x, targetX, 4, delta);
      rig.current.position.z = MathUtils.damp(rig.current.position.z, targetZ, 4, delta);
      rig.current.position.y = MathUtils.damp(rig.current.position.y, pose.y, 8, delta);
    }
  });

  return (
    <group ref={rig}>
      <primitive object={scene} />
    </group>
  );
});
