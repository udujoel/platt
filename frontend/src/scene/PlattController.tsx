import React from "react";
import { useFrame } from "@react-three/fiber";
import { MathUtils } from "three";
import { getThreeStagePose, type ThreeStageState } from "../three-stage-pose";
import { usePlattSceneStore } from "./scene-store";
import { PlattCharacter } from "./PlattCharacter";
import { clipForState, selectCrossfade } from "./crossfade";
import {
  IDLE_WAYPOINTS,
  glanceFacingOffset,
  pickDwellSeconds,
  pickIdleGesture,
  pickNextWaypoint,
  shiftSwayOffset,
  unwrapFacingAngle,
  wanderEaseLambda,
  type IdleGesture,
  type Waypoint,
} from "./waypoints";
import { PEBBLE_ORIGIN, shouldTriggerPebbleKick } from "./pebble-kick";
import type { CharacterHandle, Vector3Tuple } from "./types";

const WAYPOINT_ARRIVE_EPSILON = 0.12;
const FACING_UPDATE_MIN_DISTANCE = 0.03;

/**
 * State -> animation controller (PRD 5.3). Drives the crossfade helper, idle waypoint wander
 * (with ease in/out, a turn-to-face heading, dwell pauses with a small idle gesture, and a
 * pebble-kick roll near the pebble), and hands the character its anchor/facing/clip each frame.
 * Desk/board anchors for working/awaiting_approval already come from `three-stage-pose.ts`'s
 * per-state x offset, so the controller only overrides the anchor/facing while idle-wandering.
 */
export function PlattController() {
  const state = usePlattSceneStore((s) => s.state);
  const triggerPebbleKick = usePlattSceneStore((s) => s.triggerPebbleKick);
  const jawAmplitude = usePlattSceneStore((s) => s.jawAmplitude);
  const setHeadAnchor = usePlattSceneStore((s) => s.setHeadAnchor);

  const characterRef = React.useRef<CharacterHandle>(null);
  const previousState = React.useRef<ThreeStageState | null>(null);
  const clip = React.useMemo(() => clipForState(state), [state]);

  const currentWaypoint = React.useRef<Waypoint | null>(null);
  const wanderAnchor = React.useRef<Vector3Tuple>([0, 0, 0]);
  const facing = React.useRef(0);
  const legStartedAt = React.useRef(0);

  // Dwell = paused at a waypoint, playing out a small idle gesture before picking the next stop.
  const dwellStartedAt = React.useRef<number | null>(null);
  const dwellSeconds = React.useRef(0);
  const dwellGesture = React.useRef<IdleGesture>("none");
  const dwellOrigin = React.useRef<Vector3Tuple>([0, 0, 0]);
  const dwellBaseFacing = React.useRef(0);

  React.useEffect(() => {
    const plan = selectCrossfade(previousState.current, state);
    characterRef.current?.playClip(plan);
    previousState.current = state;
  }, [state]);

  // Don't leave a stale live anchor behind for Bubble.tsx to track forever if this controller
  // unmounts mid-wander (e.g. the character subtree remounts on an error boundary reset).
  React.useEffect(() => {
    const setHeadAnchorOnUnmount = setHeadAnchor;
    return () => setHeadAnchorOnUnmount(null);
  }, [setHeadAnchor]);

  useFrame(({ clock }, delta) => {
    characterRef.current?.setJawAmplitude(jawAmplitude);
    const elapsed = clock.getElapsedTime();

    if (state !== "idle") {
      currentWaypoint.current = null;
      dwellStartedAt.current = null;
      // Not idle-wandering: the rig sits at the canned per-state pose, which Bubble.tsx already
      // approximates exactly via getThreeStagePose, so clear the live anchor rather than publish
      // a stale idle-wander position.
      setHeadAnchor(null);
      return;
    }

    // Idle rig height stays pinned to the same constant across the whole idle wander (no bounce,
    // unlike e.g. celebrating), so this is safe to compute once per frame and reuse below.
    const idleY = getThreeStagePose("idle", elapsed).y;
    const publishHeadAnchor = () => {
      const [ax, , az] = wanderAnchor.current;
      setHeadAnchor([ax, idleY, az]);
    };

    if (!currentWaypoint.current) {
      currentWaypoint.current = pickNextWaypoint(null, IDLE_WAYPOINTS);
      legStartedAt.current = elapsed;
    }

    if (dwellStartedAt.current !== null) {
      const progress = dwellSeconds.current > 0 ? (elapsed - dwellStartedAt.current) / dwellSeconds.current : 1;
      applyDwellGesture(dwellGesture.current, progress, dwellOrigin.current, dwellBaseFacing.current, wanderAnchor, facing);
      publishHeadAnchor();
      if (elapsed - dwellStartedAt.current >= dwellSeconds.current) {
        dwellStartedAt.current = null;
        currentWaypoint.current = pickNextWaypoint(currentWaypoint.current.id, IDLE_WAYPOINTS);
        legStartedAt.current = elapsed;
      }
      return;
    }

    const [wx, , wz] = currentWaypoint.current.position;
    const [cx, cy, cz] = wanderAnchor.current;
    const dx = wx - cx;
    const dz = wz - cz;
    const distance = Math.hypot(dx, dz);

    if (distance < WAYPOINT_ARRIVE_EPSILON) {
      const distanceToPebble = Math.hypot(cx - PEBBLE_ORIGIN[0], cz - PEBBLE_ORIGIN[2]);
      if (shouldTriggerPebbleKick(distanceToPebble)) {
        triggerPebbleKick(elapsed);
      }
      dwellOrigin.current = wanderAnchor.current;
      dwellBaseFacing.current = facing.current;
      dwellGesture.current = pickIdleGesture();
      dwellSeconds.current = pickDwellSeconds();
      dwellStartedAt.current = elapsed;
      publishHeadAnchor();
      return;
    }

    if (distance > FACING_UPDATE_MIN_DISTANCE) {
      facing.current = unwrapFacingAngle(facing.current, Math.atan2(dx, dz));
    }

    const lambda = wanderEaseLambda(elapsed - legStartedAt.current);
    wanderAnchor.current = [MathUtils.damp(cx, wx, lambda, delta), cy, MathUtils.damp(cz, wz, lambda, delta)];
    publishHeadAnchor();
  });

  return (
    <PlattCharacter
      ref={characterRef}
      state={state}
      clip={clip}
      anchor={state === "idle" ? wanderAnchor : undefined}
      facing={state === "idle" ? facing : undefined}
    />
  );
}

/** Applies the current dwell gesture's offset on top of the frozen dwell origin/facing for this frame. */
function applyDwellGesture(
  gesture: IdleGesture,
  progress: number,
  origin: Vector3Tuple,
  baseFacing: number,
  anchorRef: React.MutableRefObject<Vector3Tuple>,
  facingRef: React.MutableRefObject<number>,
) {
  switch (gesture) {
    case "glance-left":
      facingRef.current = baseFacing - glanceFacingOffset(progress);
      anchorRef.current = origin;
      return;
    case "glance-right":
      facingRef.current = baseFacing + glanceFacingOffset(progress);
      anchorRef.current = origin;
      return;
    case "shift":
    case "stretch": {
      const magnitude = gesture === "stretch" ? 0.08 : 0.05;
      const [ox, oy, oz] = origin;
      const [sx, , sz] = shiftSwayOffset(progress, magnitude);
      anchorRef.current = [ox + sx, oy, oz + sz];
      facingRef.current = baseFacing;
      return;
    }
    case "none":
    default:
      anchorRef.current = origin;
      facingRef.current = baseFacing;
  }
}
