import { describe, expect, it, vi } from "vitest";

import { fetchDashboard, fetchModuleGraph } from "./dashboard-store";
import { seededDashboardData } from "./dashboard-data";
import { seededModuleGraphNodes } from "./module-graph";

function jsonResponse(body: unknown, ok = true) {
  return { ok, json: () => Promise.resolve(body) } as Response;
}

describe("fetchDashboard", () => {
  it("marks a section live and returns its real values when the backend reports source: live", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse({
        pipelines: { source: "live", series: [{ name: "real-pipeline", points: [{ label: "Mon", passRate: 100 }] }] },
        openPullRequests: { source: "live", items: [{ id: "pr-1", title: "Real PR", ageDays: 2 }] },
        versions: { source: "live", items: [{ name: "azurerm provider", current: "4.10.2", latest: "4.10.2" }] },
      }),
    );

    const result = await fetchDashboard("https://api.example.com", fetchImpl);

    expect(fetchImpl).toHaveBeenCalledWith("https://api.example.com/dashboard");
    expect(result.pipelines).toEqual({ source: "live", value: [{ name: "real-pipeline", points: [{ label: "Mon", passRate: 100 }] }] });
    expect(result.openPullRequests.source).toBe("live");
    expect(result.versions.source).toBe("live");
  });

  it("falls back to seeded values with source: unavailable when a section reports unavailable", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse({
        pipelines: { source: "unavailable" },
        openPullRequests: { source: "unavailable" },
        versions: { source: "unavailable" },
      }),
    );

    const result = await fetchDashboard("https://api.example.com", fetchImpl);

    expect(result.pipelines).toEqual({ source: "unavailable", value: seededDashboardData.pipelines });
    expect(result.openPullRequests).toEqual({ source: "unavailable", value: seededDashboardData.openPullRequests });
    expect(result.versions).toEqual({ source: "unavailable", value: seededDashboardData.versions });
  });

  it("degrades to seeded fallback when a section claims live but its payload is malformed", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      jsonResponse({
        pipelines: { source: "live", series: [{ name: "missing-points" }] },
        openPullRequests: { source: "live" },
        versions: { source: "live", items: "not-an-array" },
      }),
    );

    const result = await fetchDashboard("https://api.example.com", fetchImpl);

    expect(result.pipelines).toEqual({ source: "unavailable", value: seededDashboardData.pipelines });
    expect(result.openPullRequests).toEqual({ source: "unavailable", value: seededDashboardData.openPullRequests });
    expect(result.versions).toEqual({ source: "unavailable", value: seededDashboardData.versions });
  });

  it("degrades to seeded fallback when the request fails outright", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("network down"));

    const result = await fetchDashboard("https://api.example.com", fetchImpl);

    expect(result.pipelines).toEqual({ source: "unavailable", value: seededDashboardData.pipelines });
    expect(result.openPullRequests).toEqual({ source: "unavailable", value: seededDashboardData.openPullRequests });
    expect(result.versions).toEqual({ source: "unavailable", value: seededDashboardData.versions });
  });

  it("degrades to seeded fallback on a non-ok HTTP response", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({}, false));

    const result = await fetchDashboard("https://api.example.com", fetchImpl);

    expect(result.pipelines.source).toBe("unavailable");
  });
});

describe("fetchModuleGraph", () => {
  it("prefers the real graph when the backend reports source: live", async () => {
    const realNodes = [{ path: ".", variables: [], outputs: [], dependsOn: [] }];
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ source: "live", nodes: realNodes }));

    const result = await fetchModuleGraph("https://api.example.com", fetchImpl);

    expect(fetchImpl).toHaveBeenCalledWith("https://api.example.com/dashboard/module-graph");
    expect(result).toEqual({ source: "live", value: realNodes });
  });

  it("falls back to the seeded module graph when unavailable", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ source: "unavailable" }));

    const result = await fetchModuleGraph("https://api.example.com", fetchImpl);

    expect(result).toEqual({ source: "unavailable", value: seededModuleGraphNodes });
  });

  it("falls back to the seeded module graph when the request throws", async () => {
    const fetchImpl = vi.fn().mockRejectedValue(new Error("network down"));

    const result = await fetchModuleGraph("https://api.example.com", fetchImpl);

    expect(result).toEqual({ source: "unavailable", value: seededModuleGraphNodes });
  });
});
