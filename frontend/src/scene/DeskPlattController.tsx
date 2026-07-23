import React from "react";
import { useFrame } from "@react-three/fiber";
import type { ThreeStageState } from "../three-stage-pose";
import { usePlattSceneStore } from "./scene-store";
import { PlattCharacter } from "./PlattCharacter";
import { clipForState, selectCrossfade } from "./crossfade";
import type { CharacterHandle, Vector3Tuple } from "./types";

/** Seat anchor (x, y, z): keeps Platt pinned at the desk chair instead of the full-room idle wander. */
const DESK_SEAT_ANCHOR: Vector3Tuple = [0, 0, -0.1];
const DESK_SWAY_AMPLITUDE = 0.03;
const DESK_SWAY_HZ = 0.16;

/**
 * Desk-widget analogue of `PlattController`: same state -> crossfade + jaw-amplitude wiring
 * (reusing `crossfade.ts` and the shared `PlattCharacter` glb/procedural + relay stack per the
 * `CharacterHandle` contract), but swaps the full-room idle waypoint wander for a small in-place
 * sway so Platt stays seated at the desk in this compact corner widget instead of walking off
 * frame.
 */
export function DeskPlattController() {
  const state = usePlattSceneStore((s) => s.state);
  const jawAmplitude = usePlattSceneStore((s) => s.jawAmplitude);

  const characterRef = React.useRef<CharacterHandle>(null);
  const previousState = React.useRef<ThreeStageState | null>(null);
  const clip = React.useMemo(() => clipForState(state), [state]);
  const anchor = React.useRef<Vector3Tuple>(DESK_SEAT_ANCHOR);

  React.useEffect(() => {
    const plan = selectCrossfade(previousState.current, state);
    characterRef.current?.playClip(plan);
    previousState.current = state;
  }, [state]);

  useFrame(({ clock }) => {
    characterRef.current?.setJawAmplitude(jawAmplitude);
    const t = clock.getElapsedTime();
    const [ax, ay, az] = DESK_SEAT_ANCHOR;
    anchor.current = [ax + Math.sin(t * DESK_SWAY_HZ * Math.PI * 2) * DESK_SWAY_AMPLITUDE, ay, az];
  });

  return <PlattCharacter ref={characterRef} state={state} clip={clip} anchor={anchor} />;
}
