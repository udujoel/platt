import { describe, expect, it } from "vitest";

import { averagePassRate, formatAge, isVersionCurrent, seededDashboardData } from "./dashboard-data";

describe("seededDashboardData", () => {
  it("is marked as seeded so the UI can label it", () => {
    expect(seededDashboardData.seeded).toBe(true);
  });

  it("does not fabricate PR URLs for seeded pull requests, keeping them non-navigable sample data", () => {
    expect(seededDashboardData.openPullRequests.length).toBeGreaterThan(0);
    for (const pr of seededDashboardData.openPullRequests) {
      expect(pr.url).toBeUndefined();
    }
  });
});

describe("averagePassRate", () => {
  it("averages the pass-rate points for a pipeline series", () => {
    const average = averagePassRate({ name: "p", points: [{ label: "a", passRate: 80 }, { label: "b", passRate: 100 }] });
    expect(average).toBe(90);
  });

  it("returns 0 for a series with no data", () => {
    expect(averagePassRate({ name: "p", points: [] })).toBe(0);
  });
});

describe("formatAge", () => {
  it("pluralizes days correctly", () => {
    expect(formatAge(1)).toBe("1 day old");
    expect(formatAge(4)).toBe("4 days old");
  });
});

describe("isVersionCurrent", () => {
  it("flags a module that matches its latest version", () => {
    expect(isVersionCurrent({ name: "m", current: "1.0.0", latest: "1.0.0" })).toBe(true);
    expect(isVersionCurrent({ name: "m", current: "1.0.0", latest: "1.1.0" })).toBe(false);
  });
});
