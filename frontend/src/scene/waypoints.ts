import type { Vector3Tuple } from "./types";

export type Waypoint = { id: string; position: Vector3Tuple };

/** Room-relative idle wander stops, kept clear of the desk/board anchors and server rack. */
export const IDLE_WAYPOINTS: Waypoint[] = [
  { id: "desk-side", position: [1.1, 0, -0.1] },
  { id: "plant-corner", position: [-2.6, 0, -0.2] },
  { id: "board-front", position: [-2.2, 0, -1.6] },
  { id: "rack-side", position: [2.0, 0, -1.3] },
  { id: "center", position: [0, 0, 0.6] },
];

/** Picks a random waypoint different from the current one (pure; caller supplies rng for determinism). */
export function pickNextWaypoint(
  currentId: string | null,
  waypoints: Waypoint[] = IDLE_WAYPOINTS,
  rng: () => number = Math.random,
): Waypoint {
  if (waypoints.length === 0) {
    throw new Error("pickNextWaypoint requires a non-empty waypoint list");
  }
  const candidates = waypoints.filter((waypoint) => waypoint.id !== currentId);
  const pool = candidates.length > 0 ? candidates : waypoints;
  const index = Math.min(pool.length - 1, Math.floor(rng() * pool.length));
  return pool[index];
}

export const IDLE_DWELL_MIN_SECONDS = 1.2;
export const IDLE_DWELL_MAX_SECONDS = 3.6;

/**
 * Randomized pause length after arriving at a waypoint (pure; caller supplies rng for
 * determinism), so idle wander reads as someone pausing to look around rather than a
 * metronome ticking between fixed stops.
 */
export function pickDwellSeconds(
  rng: () => number = Math.random,
  min: number = IDLE_DWELL_MIN_SECONDS,
  max: number = IDLE_DWELL_MAX_SECONDS,
): number {
  return min + rng() * (max - min);
}

export type IdleGesture = "none" | "glance-left" | "glance-right" | "shift" | "stretch";

/** Weighted so "none" (just standing) is still the most common outcome, gestures are a garnish. */
const IDLE_GESTURES: IdleGesture[] = ["none", "none", "none", "glance-left", "glance-right", "shift", "stretch"];

/** Picks the idle gesture to play during a waypoint dwell (pure; caller supplies rng for determinism). */
export function pickIdleGesture(rng: () => number = Math.random): IdleGesture {
  const index = Math.min(IDLE_GESTURES.length - 1, Math.floor(rng() * IDLE_GESTURES.length));
  return IDLE_GESTURES[index];
}

/**
 * Damp lambda for a wander leg: ramps up from a stand-still over `rampSeconds` so a fresh leg
 * eases into motion, then holds `baseLambda` for the rest of the leg. `MathUtils.damp` already
 * gives exponential ease-out as the anchor nears its target, so this only needs to cover ease-in.
 */
export function wanderEaseLambda(elapsedSinceLegStart: number, baseLambda = 3.2, rampSeconds = 0.4): number {
  const ramp = Math.min(1, Math.max(0, elapsedSinceLegStart / rampSeconds));
  return baseLambda * ramp;
}

/**
 * Unwraps a new `Math.atan2`-derived heading (range `(-π, π]`) to the value nearest `previous`,
 * so a `MathUtils.damp` toward the result always takes the shortest turn instead of occasionally
 * spinning the long way around when a wander leg's heading straddles the ±π seam.
 */
export function unwrapFacingAngle(previous: number, target: number): number {
  const twoPi = Math.PI * 2;
  let delta = (target - previous) % twoPi;
  if (delta > Math.PI) delta -= twoPi;
  if (delta < -Math.PI) delta += twoPi;
  return previous + delta;
}

/** Symmetric ease-in/ease-out envelope (0 -> 1 -> 0) over a 0..1 progress value. */
function easeInOutEnvelope(progress: number): number {
  const t = Math.min(1, Math.max(0, progress));
  return Math.sin(Math.PI * t);
}

/** Temporary head/facing offset (radians) for a glance gesture; peaks mid-dwell, settles back to 0. */
export function glanceFacingOffset(progress: number, magnitude = 0.55): number {
  return magnitude * easeInOutEnvelope(progress);
}

/** Small weight-shift/stretch sway (meters) added on top of the dwell anchor position. */
export function shiftSwayOffset(progress: number, magnitude = 0.05): Vector3Tuple {
  const envelope = easeInOutEnvelope(progress);
  const t = Math.min(1, Math.max(0, progress));
  return [Math.sin(t * Math.PI * 2) * magnitude * envelope, 0, Math.cos(t * Math.PI * 2) * magnitude * envelope * 0.4];
}
