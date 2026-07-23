import { describe, expect, it } from "vitest";

import {
  activeWorkItemsCount,
  alertEntryCount,
  auditRunsByDay,
  classifyAuditSeverity,
  clampPercent,
  cumulativeActivity,
  outcomeBreakdown,
  overallPassRate,
  pendingApprovalsCount,
  versionPostureLabel,
  versionsBehindCount,
} from "./dashboard-metrics";
import type { AuditEntry } from "./dashboard-metrics";
import type { ApprovalEntry } from "./approval-store";
import type { WorkItem } from "./kanban-store";
import type { PipelineSeries, VersionPosture } from "./dashboard-data";

const auditEntry = (overrides: Partial<AuditEntry>): AuditEntry => ({
  id: 1,
  job_id: "job-1",
  tool: "terraform",
  action: "apply",
  outcome: "success",
  created_at: "2026-07-20T10:00:00.000Z",
  ...overrides,
});

describe("classifyAuditSeverity", () => {
  it("flags failure language as critical", () => {
    expect(classifyAuditSeverity("apply failed")).toBe("critical");
    expect(classifyAuditSeverity("Approval rejected")).toBe("critical");
  });

  it("flags cautionary language as warning", () => {
    expect(classifyAuditSeverity("retrying after timeout")).toBe("warning");
  });

  it("defaults to info", () => {
    expect(classifyAuditSeverity("success")).toBe("info");
  });
});

describe("alertEntryCount", () => {
  it("only counts warning/critical entries, not the full audit trail", () => {
    const entries: AuditEntry[] = [
      auditEntry({ id: 1, outcome: "success" }),
      auditEntry({ id: 2, outcome: "apply failed" }),
      auditEntry({ id: 3, outcome: "retry after timeout" }),
      auditEntry({ id: 4, outcome: "success" }),
    ];
    expect(alertEntryCount(entries)).toBe(2);
  });

  it("returns 0 when nothing is alert-severity", () => {
    const entries: AuditEntry[] = [auditEntry({ id: 1, outcome: "success" })];
    expect(alertEntryCount(entries)).toBe(0);
  });
});

describe("pendingApprovalsCount", () => {
  it("counts only pending entries", () => {
    const entries: ApprovalEntry[] = [
      { id: "a", jobId: "j", summary: "s", status: "pending", deciding: false, error: null },
      { id: "b", jobId: "j", summary: "s", status: "approved", deciding: false, error: null },
    ];
    expect(pendingApprovalsCount(entries)).toBe(1);
  });
});

describe("activeWorkItemsCount", () => {
  it("counts items in the Doing column", () => {
    const items: WorkItem[] = [
      { id: "1", jobId: "j", title: "a", column: "Doing", updatedAt: "" },
      { id: "2", jobId: "j", title: "b", column: "Done", updatedAt: "" },
      { id: "3", jobId: "j", title: "c", column: "Doing", updatedAt: "" },
    ];
    expect(activeWorkItemsCount(items)).toBe(2);
  });
});

describe("versionsBehindCount / versionPostureLabel", () => {
  const versions: VersionPosture[] = [
    { name: "a", current: "1.0", latest: "1.0" },
    { name: "b", current: "1.0", latest: "1.2" },
  ];

  it("counts non-current versions", () => {
    expect(versionsBehindCount(versions)).toBe(1);
  });

  it("labels the current/total ratio", () => {
    expect(versionPostureLabel(versions)).toBe("1/2 current");
  });
});

describe("overallPassRate", () => {
  it("averages per-series pass rates", () => {
    const pipelines: PipelineSeries[] = [
      { name: "a", points: [{ label: "x", passRate: 100 }] },
      { name: "b", points: [{ label: "x", passRate: 50 }] },
    ];
    expect(overallPassRate(pipelines)).toBe(75);
  });

  it("returns 0 with no pipelines", () => {
    expect(overallPassRate([])).toBe(0);
  });
});

describe("auditRunsByDay / cumulativeActivity", () => {
  const now = new Date("2026-07-23T12:00:00.000Z");
  const entries: AuditEntry[] = [
    auditEntry({ id: 1, created_at: "2026-07-22T10:00:00.000Z" }),
    auditEntry({ id: 2, created_at: "2026-07-22T11:00:00.000Z" }),
    auditEntry({ id: 3, created_at: "2026-07-23T09:00:00.000Z" }),
  ];

  it("buckets entries into trailing days", () => {
    const points = auditRunsByDay(entries, 3, now);
    expect(points).toHaveLength(3);
    expect(points[points.length - 1].count).toBe(1);
    expect(points[points.length - 2].count).toBe(2);
  });

  it("accumulates running totals across the window", () => {
    const points = cumulativeActivity(entries, 3, now);
    expect(points[points.length - 1].count).toBe(3);
    expect(points[0].count).toBeLessThanOrEqual(points[points.length - 1].count);
  });
});

describe("outcomeBreakdown", () => {
  it("buckets audit outcomes into success/warning/failure", () => {
    const entries: AuditEntry[] = [
      auditEntry({ id: 1, outcome: "success" }),
      auditEntry({ id: 2, outcome: "apply failed" }),
      auditEntry({ id: 3, outcome: "retry after timeout" }),
      auditEntry({ id: 4, outcome: "success" }),
    ];
    expect(outcomeBreakdown(entries)).toEqual([
      { name: "Success", value: 2 },
      { name: "Warning", value: 1 },
      { name: "Failure", value: 1 },
    ]);
  });

  it("omits empty slices", () => {
    const entries: AuditEntry[] = [auditEntry({ id: 1, outcome: "success" })];
    expect(outcomeBreakdown(entries)).toEqual([{ name: "Success", value: 1 }]);
  });
});

describe("clampPercent", () => {
  it("clamps into 0..100 and rounds", () => {
    expect(clampPercent(-5)).toBe(0);
    expect(clampPercent(120)).toBe(100);
    expect(clampPercent(42.6)).toBe(43);
  });
});
