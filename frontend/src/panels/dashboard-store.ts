import { create } from "zustand";
import type { OpenPullRequest, PipelineSeries, VersionPosture } from "./dashboard-data";
import { seededDashboardData } from "./dashboard-data";
import type { ModuleGraphNode } from "./module-graph";
import { seededModuleGraphNodes } from "./module-graph";

export type DataSource = "live" | "unavailable";

export type Sourced<T> = { source: DataSource; value: T };

/** Cheap enough to poll: one small JSON GET per section, no websockets. */
export const DASHBOARD_REFRESH_INTERVAL_MS = 30_000;

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isPipelineSeries(value: unknown): value is PipelineSeries {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    Array.isArray(value.points) &&
    value.points.every((point) => isRecord(point) && typeof point.label === "string" && typeof point.passRate === "number")
  );
}

function isOpenPullRequest(value: unknown): value is OpenPullRequest {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.title === "string" &&
    typeof value.ageDays === "number" &&
    (value.url === undefined || typeof value.url === "string")
  );
}

function isVersionPosture(value: unknown): value is VersionPosture {
  return isRecord(value) && typeof value.name === "string" && typeof value.current === "string" && typeof value.latest === "string";
}

function isModuleGraphNode(value: unknown): value is ModuleGraphNode {
  return (
    isRecord(value) &&
    typeof value.path === "string" &&
    Array.isArray(value.variables) &&
    value.variables.every((item) => typeof item === "string") &&
    Array.isArray(value.outputs) &&
    value.outputs.every((item) => typeof item === "string") &&
    Array.isArray(value.dependsOn) &&
    value.dependsOn.every((item) => typeof item === "string")
  );
}

/**
 * A dashboard section is only trusted as "live" when it both declares
 * `source: "live"` AND its payload matches the expected shape — a section
 * that claims to be live but sends malformed data degrades to the seeded
 * fallback rather than rendering garbage as if it were real.
 */
function parseSourcedArray<T>(
  section: unknown,
  arrayKey: string,
  itemGuard: (item: unknown) => item is T,
  fallback: T[],
): Sourced<T[]> {
  if (!isRecord(section) || (section.source !== "live" && section.source !== "unavailable")) {
    return { source: "unavailable", value: fallback };
  }
  const items = section[arrayKey];
  if (section.source !== "live" || !Array.isArray(items) || !items.every(itemGuard)) {
    return { source: "unavailable", value: fallback };
  }
  return { source: "live", value: items };
}

export type DashboardPayload = {
  pipelines: Sourced<PipelineSeries[]>;
  openPullRequests: Sourced<OpenPullRequest[]>;
  versions: Sourced<VersionPosture[]>;
};

const dashboardFallback: DashboardPayload = {
  pipelines: { source: "unavailable", value: seededDashboardData.pipelines },
  openPullRequests: { source: "unavailable", value: seededDashboardData.openPullRequests },
  versions: { source: "unavailable", value: seededDashboardData.versions },
};

const moduleGraphFallback: Sourced<ModuleGraphNode[]> = { source: "unavailable", value: seededModuleGraphNodes };

export async function fetchDashboard(apiBaseUrl: string, fetchImpl: typeof fetch = fetch): Promise<DashboardPayload> {
  try {
    const response = await fetchImpl(`${apiBaseUrl}/dashboard`);
    if (!response.ok) return dashboardFallback;
    const payload: unknown = await response.json();
    if (!isRecord(payload)) return dashboardFallback;
    return {
      pipelines: parseSourcedArray(payload.pipelines, "series", isPipelineSeries, seededDashboardData.pipelines),
      openPullRequests: parseSourcedArray(payload.openPullRequests, "items", isOpenPullRequest, seededDashboardData.openPullRequests),
      versions: parseSourcedArray(payload.versions, "items", isVersionPosture, seededDashboardData.versions),
    };
  } catch {
    return dashboardFallback;
  }
}

export async function fetchModuleGraph(apiBaseUrl: string, fetchImpl: typeof fetch = fetch): Promise<Sourced<ModuleGraphNode[]>> {
  try {
    const response = await fetchImpl(`${apiBaseUrl}/dashboard/module-graph`);
    if (!response.ok) return moduleGraphFallback;
    const payload: unknown = await response.json();
    return parseSourcedArray(payload, "nodes", isModuleGraphNode, seededModuleGraphNodes);
  } catch {
    return moduleGraphFallback;
  }
}

type DashboardStore = DashboardPayload & {
  moduleGraph: Sourced<ModuleGraphNode[]>;
  refresh: (apiBaseUrl: string) => Promise<void>;
};

export const useDashboardStore = create<DashboardStore>((set) => ({
  ...dashboardFallback,
  moduleGraph: moduleGraphFallback,
  refresh: async (apiBaseUrl) => {
    const [dashboard, moduleGraph] = await Promise.all([fetchDashboard(apiBaseUrl), fetchModuleGraph(apiBaseUrl)]);
    set({ ...dashboard, moduleGraph });
  },
}));
