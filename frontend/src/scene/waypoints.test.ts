import { describe, expect, it } from "vitest";

import { IDLE_WAYPOINTS, pickNextWaypoint } from "./waypoints";

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
});
