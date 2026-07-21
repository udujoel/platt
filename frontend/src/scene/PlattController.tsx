import React from "react";
import { useFrame } from "@react-three/fiber";
import type { ThreeStageState } from "../three-stage-pose";
import { usePlattSceneStore } from "./scene-store";
import { PlattCharacter } from "./PlattCharacter";
import { clipForState, selectCrossfade } from "./crossfade";
import { IDLE_WAYPOINTS, pickNextWaypoint, type Waypoint } from "./waypoints";
import { PEBBLE_ORIGIN, shouldTriggerPebbleKick } from "./pebble-kick";
import type { CharacterHandle, Vector3Tuple } from "./types";

const WANDER_SPEED = 0.9;
const WAYPOINT_ARRIVE_EPSILON = 0.12;

/**
 * State -> animation controller (PRD 5.3). Drives the crossfade helper, idle waypoint wander
 * (with a pebble-kick roll near the pebble), and hands the character its anchor/clip each frame.
 * Desk/board anchors for working/awaiting_approval already come from `three-stage-pose.ts`'s
 * per-state x offset, so the controller only overrides the anchor while idle-wandering.
 */
export function PlattController() {
  const state = usePlattSceneStore((s) => s.state);
  const triggerPebbleKick = usePlattSceneStore((s) => s.triggerPebbleKick);

  const characterRef = React.useRef<CharacterHandle>(null);
  const previousState = React.useRef<ThreeStageState | null>(null);
  const clip = React.useMemo(() => clipForState(state), [state]);

  const currentWaypoint = React.useRef<Waypoint | null>(null);
  const wanderAnchor = React.useRef<Vector3Tuple>([0, 0, 0]);

  React.useEffect(() => {
    const plan = selectCrossfade(previousState.current, state);
    characterRef.current?.playClip(plan);
    previousState.current = state;
  }, [state]);

  useFrame(({ clock }, delta) => {
    if (state !== "idle") {
      currentWaypoint.current = null;
      return;
    }
    if (!currentWaypoint.current) {
      currentWaypoint.current = pickNextWaypoint(null, IDLE_WAYPOINTS);
    }

    const [wx, , wz] = currentWaypoint.current.position;
    const [cx, cy, cz] = wanderAnchor.current;
    const dx = wx - cx;
    const dz = wz - cz;
    const distance = Math.hypot(dx, dz);

    if (distance < WAYPOINT_ARRIVE_EPSILON) {
      const distanceToPebble = Math.hypot(cx - PEBBLE_ORIGIN[0], cz - PEBBLE_ORIGIN[2]);
      if (shouldTriggerPebbleKick(distanceToPebble)) {
        triggerPebbleKick(clock.getElapsedTime());
      }
      currentWaypoint.current = pickNextWaypoint(currentWaypoint.current.id, IDLE_WAYPOINTS);
      return;
    }

    const step = Math.min(distance, WANDER_SPEED * delta);
    wanderAnchor.current = [cx + (dx / distance) * step, cy, cz + (dz / distance) * step];
  });

  return <PlattCharacter ref={characterRef} state={state} clip={clip} anchor={state === "idle" ? wanderAnchor : undefined} />;
}
