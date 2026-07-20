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
  const candidates = waypoints.filter((waypoint) => waypoint.id !== currentId);
  const pool = candidates.length > 0 ? candidates : waypoints;
  const index = Math.min(pool.length - 1, Math.floor(rng() * pool.length));
  return pool[index];
}
