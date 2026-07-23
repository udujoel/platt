import type { PipelineSeries, VersionPosture } from "./dashboard-data";
import { averagePassRate, isVersionCurrent } from "./dashboard-data";
import type { ApprovalEntry } from "./approval-store";
import type { WorkItem } from "./kanban-store";

export type AuditEntry = {
  id: number;
  job_id: string | null;
  tool: string;
  action: string;
  outcome: string;
  created_at: string;
};

export type Severity = "info" | "warning" | "critical";

const criticalMarkers = ["fail", "error", "denied", "reject"];
const warningMarkers = ["warn", "retry", "timeout", "pending"];

/**
 * Audit entries carry a free-text outcome (no severity field), so this
 * classifies by substring the same way kanban-store buckets Boards states.
 */
export function classifyAuditSeverity(outcome: string): Severity {
  const normalized = outcome.trim().toLowerCase();
  if (criticalMarkers.some((marker) => normalized.includes(marker))) return "critical";
  if (warningMarkers.some((marker) => normalized.includes(marker))) return "warning";
  return "info";
}

export function pendingApprovalsCount(entries: ApprovalEntry[]): number {
  return entries.filter((entry) => entry.status === "pending").length;
}

export function activeWorkItemsCount(items: WorkItem[]): number {
  return items.filter((item) => item.column === "Doing").length;
}

export function versionsBehindCount(versions: VersionPosture[]): number {
  return versions.filter((version) => !isVersionCurrent(version)).length;
}

export function versionPostureLabel(versions: VersionPosture[]): string {
  const current = versions.length - versionsBehindCount(versions);
  return `${current}/${versions.length} current`;
}

export function overallPassRate(pipelines: PipelineSeries[]): number {
  if (pipelines.length === 0) return 0;
  const total = pipelines.reduce((sum, series) => sum + averagePassRate(series), 0);
  return Math.round(total / pipelines.length);
}

function dayKey(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  return Number.isNaN(date.getTime()) ? "unknown" : date.toISOString().slice(0, 10);
}

function dayLabel(dayIso: string): string {
  const date = new Date(`${dayIso}T00:00:00Z`);
  return Number.isNaN(date.getTime()) ? dayIso : date.toLocaleDateString([], { weekday: "short" });
}

/** Trailing window of `days` UTC calendar days ending today, oldest first. */
function trailingDayKeys(days: number, today: Date): string[] {
  const keys: string[] = [];
  for (let offset = days - 1; offset >= 0; offset -= 1) {
    const date = new Date(today);
    date.setUTCDate(date.getUTCDate() - offset);
    keys.push(date.toISOString().slice(0, 10));
  }
  return keys;
}

export type DayPoint = { label: string; count: number };

/** Runs-by-day: per-day audit entry volume, most recent `days` days. */
export function auditRunsByDay(entries: AuditEntry[], days = 7, now: Date = new Date()): DayPoint[] {
  const counts = new Map<string, number>();
  for (const entry of entries) {
    const key = dayKey(entry.created_at);
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return trailingDayKeys(days, now).map((key) => ({ label: dayLabel(key), count: counts.get(key) ?? 0 }));
}

/** Activity-over-time: cumulative audit entry count across the trailing window, for trend reading. */
export function cumulativeActivity(entries: AuditEntry[], days = 7, now: Date = new Date()): DayPoint[] {
  const perDay = auditRunsByDay(entries, days, now);
  let running = 0;
  return perDay.map((point) => {
    running += point.count;
    return { label: point.label, count: running };
  });
}

export type OutcomeSlice = { name: string; value: number };

/** Job-outcome breakdown for the donut: success / warning / failure counts from audit outcomes. */
export function outcomeBreakdown(entries: AuditEntry[]): OutcomeSlice[] {
  let success = 0;
  let warning = 0;
  let failure = 0;
  for (const entry of entries) {
    const severity = classifyAuditSeverity(entry.outcome);
    if (severity === "critical") failure += 1;
    else if (severity === "warning") warning += 1;
    else success += 1;
  }
  return [
    { name: "Success", value: success },
    { name: "Warning", value: warning },
    { name: "Failure", value: failure },
  ].filter((slice) => slice.value > 0);
}

export function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}
