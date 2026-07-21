export type PipelineRunPoint = { label: string; passRate: number };

export type PipelineSeries = {
  name: string;
  points: PipelineRunPoint[];
};

export type OpenPullRequest = {
  id: string;
  title: string;
  ageDays: number;
  url: string;
};

export type VersionPosture = {
  name: string;
  current: string;
  latest: string;
};

export type DashboardData = {
  seeded: boolean;
  pipelines: PipelineSeries[];
  openPullRequests: OpenPullRequest[];
  versions: VersionPosture[];
};

/**
 * Real collectors (Azure Boards/pipelines/version APIs) land in a later
 * wave; this seeded snapshot keeps the dashboard shape stable for the UI.
 */
export const seededDashboardData: DashboardData = {
  seeded: true,
  pipelines: [
    {
      name: "terraform-plan-sandbox",
      points: [
        { label: "Mon", passRate: 88 },
        { label: "Tue", passRate: 91 },
        { label: "Wed", passRate: 76 },
        { label: "Thu", passRate: 94 },
        { label: "Fri", passRate: 97 },
      ],
    },
    {
      name: "terraform-apply-sandbox",
      points: [
        { label: "Mon", passRate: 100 },
        { label: "Tue", passRate: 100 },
        { label: "Wed", passRate: 82 },
        { label: "Thu", passRate: 90 },
        { label: "Fri", passRate: 100 },
      ],
    },
  ],
  openPullRequests: [
    { id: "pr-142", title: "Add storage account for onboarding docs", ageDays: 1, url: "https://dev.azure.com/_git/pr/142" },
    { id: "pr-139", title: "Bump azurerm to ~> 4.10", ageDays: 4, url: "https://dev.azure.com/_git/pr/139" },
    { id: "pr-131", title: "Widen sandbox vnet address space", ageDays: 9, url: "https://dev.azure.com/_git/pr/131" },
  ],
  versions: [
    { name: "azurerm provider", current: "4.4.0", latest: "4.10.2" },
    { name: "module: storage-account", current: "2.3.0", latest: "2.3.0" },
    { name: "module: networking", current: "1.8.1", latest: "1.9.0" },
  ],
};

export function isVersionCurrent(version: VersionPosture): boolean {
  return version.current === version.latest;
}

export function averagePassRate(series: PipelineSeries): number {
  if (series.points.length === 0) return 0;
  const total = series.points.reduce((sum, point) => sum + point.passRate, 0);
  return Math.round(total / series.points.length);
}

export function formatAge(ageDays: number): string {
  return ageDays === 1 ? "1 day old" : `${ageDays} days old`;
}
