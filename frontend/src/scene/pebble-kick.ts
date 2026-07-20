import type { Vector3Tuple } from "./types";

export const PEBBLE_KICK_DURATION_SECONDS = 0.9;
export const PEBBLE_KICK_ARC_HEIGHT = 0.6;
export const PEBBLE_ORIGIN: Vector3Tuple = [-0.25, 0.18, 0.5];
export const PEBBLE_TARGET: Vector3Tuple = [-1.1, 0.18, 1.1];

/** Parabolic arc position for the kicked pebble at elapsed seconds since the kick started. */
export function pebbleArcPosition(
  origin: Vector3Tuple,
  target: Vector3Tuple,
  elapsedSeconds: number,
  durationSeconds: number = PEBBLE_KICK_DURATION_SECONDS,
): Vector3Tuple {
  const t = Math.min(Math.max(elapsedSeconds / durationSeconds, 0), 1);
  const x = origin[0] + (target[0] - origin[0]) * t;
  const z = origin[2] + (target[2] - origin[2]) * t;
  const y = origin[1] + (target[1] - origin[1]) * t + PEBBLE_KICK_ARC_HEIGHT * Math.sin(Math.PI * t);
  return [x, y, z];
}

export function isPebbleKickComplete(
  elapsedSeconds: number,
  durationSeconds: number = PEBBLE_KICK_DURATION_SECONDS,
): boolean {
  return elapsedSeconds >= durationSeconds;
}

/** Rolls a kick chance when idle wander passes near the pebble (pure; caller supplies rng for determinism). */
export function shouldTriggerPebbleKick(
  distanceToPebble: number,
  rng: () => number = Math.random,
  chance = 0.35,
  proximity = 0.6,
): boolean {
  return distanceToPebble <= proximity && rng() < chance;
}
