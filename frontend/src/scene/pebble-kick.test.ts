import { describe, expect, it } from "vitest";

import {
  PEBBLE_KICK_DURATION_SECONDS,
  isPebbleKickComplete,
  pebbleArcPosition,
  shouldTriggerPebbleKick,
} from "./pebble-kick";

describe("pebbleArcPosition", () => {
  const origin: [number, number, number] = [0, 0, 0];
  const target: [number, number, number] = [2, 0, 4];

  it("starts at the origin and ends at the target", () => {
    expect(pebbleArcPosition(origin, target, 0)).toEqual([0, 0, 0]);
    const end = pebbleArcPosition(origin, target, PEBBLE_KICK_DURATION_SECONDS);
    expect(end[0]).toBeCloseTo(2);
    expect(end[2]).toBeCloseTo(4);
  });

  it("arcs above a straight line at the midpoint", () => {
    const mid = pebbleArcPosition(origin, target, PEBBLE_KICK_DURATION_SECONDS / 2);
    expect(mid[1]).toBeGreaterThan(0);
  });

  it("clamps past the kick duration", () => {
    const overshoot = pebbleArcPosition(origin, target, PEBBLE_KICK_DURATION_SECONDS * 5);
    expect(overshoot[0]).toBeCloseTo(2);
    expect(overshoot[1]).toBeCloseTo(0);
  });
});

describe("isPebbleKickComplete", () => {
  it("flags completion at and past the duration", () => {
    expect(isPebbleKickComplete(PEBBLE_KICK_DURATION_SECONDS - 0.01)).toBe(false);
    expect(isPebbleKickComplete(PEBBLE_KICK_DURATION_SECONDS)).toBe(true);
  });
});

describe("shouldTriggerPebbleKick", () => {
  it("never triggers outside the proximity radius", () => {
    expect(shouldTriggerPebbleKick(10, () => 0)).toBe(false);
  });

  it("rolls the chance inside the proximity radius", () => {
    expect(shouldTriggerPebbleKick(0.1, () => 0)).toBe(true);
    expect(shouldTriggerPebbleKick(0.1, () => 0.99)).toBe(false);
  });
});
