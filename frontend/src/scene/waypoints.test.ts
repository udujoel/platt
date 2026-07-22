import { describe, expect, it } from "vitest";

import {
  IDLE_DWELL_MAX_SECONDS,
  IDLE_DWELL_MIN_SECONDS,
  IDLE_WAYPOINTS,
  glanceFacingOffset,
  pickDwellSeconds,
  pickIdleGesture,
  pickNextWaypoint,
  shiftSwayOffset,
  wanderEaseLambda,
} from "./waypoints";

describe("pickNextWaypoint", () => {
  it("picks deterministically from the rng", () => {
    expect(pickNextWaypoint(null, IDLE_WAYPOINTS, () => 0)).toEqual(IDLE_WAYPOINTS[0]);
    expect(pickNextWaypoint(null, IDLE_WAYPOINTS, () => 0.999)).toEqual(IDLE_WAYPOINTS[IDLE_WAYPOINTS.length - 1]);
  });

  it("never re-picks the current waypoint", () => {
    for (let i = 0; i < IDLE_WAYPOINTS.length; i += 1) {
      const rng = () => i / IDLE_WAYPOINTS.length;
      const next = pickNextWaypoint(IDLE_WAYPOINTS[i].id, IDLE_WAYPOINTS, rng);
      expect(next.id).not.toBe(IDLE_WAYPOINTS[i].id);
    }
  });

  it("falls back to the full list when every waypoint is excluded", () => {
    const single = [IDLE_WAYPOINTS[0]];
    expect(pickNextWaypoint(single[0].id, single, () => 0)).toEqual(single[0]);
  });

  it("throws instead of returning undefined for an empty waypoint list", () => {
    expect(() => pickNextWaypoint(null, [], () => 0)).toThrow(/non-empty/);
  });
});

describe("pickDwellSeconds", () => {
  it("stays within the configured min/max range", () => {
    expect(pickDwellSeconds(() => 0)).toBe(IDLE_DWELL_MIN_SECONDS);
    expect(pickDwellSeconds(() => 1)).toBeCloseTo(IDLE_DWELL_MAX_SECONDS);
  });

  it("honors a custom range", () => {
    expect(pickDwellSeconds(() => 0.5, 1, 3)).toBeCloseTo(2);
  });
});

describe("pickIdleGesture", () => {
  it("picks deterministically from the rng, weighted toward 'none'", () => {
    expect(pickIdleGesture(() => 0)).toBe("none");
    expect(pickIdleGesture(() => 0.999)).toBe("stretch");
  });
});

describe("wanderEaseLambda", () => {
  it("starts at zero and ramps up to the base lambda over rampSeconds", () => {
    expect(wanderEaseLambda(0)).toBe(0);
    expect(wanderEaseLambda(0.2, 3.2, 0.4)).toBeCloseTo(1.6);
    expect(wanderEaseLambda(0.4, 3.2, 0.4)).toBeCloseTo(3.2);
  });

  it("clamps at the base lambda past rampSeconds", () => {
    expect(wanderEaseLambda(10, 3.2, 0.4)).toBe(3.2);
  });
});

describe("glanceFacingOffset", () => {
  it("starts and ends at zero, peaking mid-dwell", () => {
    expect(glanceFacingOffset(0)).toBeCloseTo(0);
    expect(glanceFacingOffset(1)).toBeCloseTo(0);
    expect(glanceFacingOffset(0.5, 0.55)).toBeCloseTo(0.55);
  });
});

describe("shiftSwayOffset", () => {
  it("returns a zero offset at the start and end of the dwell", () => {
    expect(shiftSwayOffset(0)).toEqual([0, 0, 0]);
    const end = shiftSwayOffset(1);
    expect(end[0]).toBeCloseTo(0);
    expect(end[2]).toBeCloseTo(0);
  });

  it("sways away from the origin mid-dwell", () => {
    const mid = shiftSwayOffset(0.25, 0.05);
    expect(Math.hypot(mid[0], mid[2])).toBeGreaterThan(0);
  });
});
