import React from "react";
import { Activity, GitPullRequest, GitBranch, ShieldCheck, Timer, TrendingUp } from "lucide-react";
import { KpiTile } from "./KpiTile";
import { GaugeCard } from "./GaugeCard";
import { ActivityLineCard } from "./ActivityLineCard";
import { RunsBarCard } from "./RunsBarCard";
import { OutcomesDonutCard } from "./OutcomesDonutCard";
import { AlertsFeed } from "./AlertsFeed";
import { ModuleGraphCard } from "./ModuleGraphCard";
import { ProvisioningCard } from "./ProvisioningCard";
import { ApprovalGate } from "./ApprovalCard";
import { EventFeedCard } from "./EventFeedCard";
import type { FeedEvent } from "./EventFeedCard";
import {
  activeWorkItemsCount,
  auditRunsByDay,
  cumulativeActivity,
  outcomeBreakdown,
  overallPassRate,
  pendingApprovalsCount,
  versionPostureLabel,
  versionsBehindCount,
} from "./dashboard-metrics";
import type { AuditEntry } from "./dashboard-metrics";
import { useDashboardStore } from "./dashboard-store";
import { useApprovalStore } from "./approval-store";
import { useKanbanStore } from "./kanban-store";
import type { BackendEvent } from "../backend-events";

export function OverviewView({
  apiBaseUrl,
  lastEvent,
  audit,
  onSelectJob,
  events,
  connection,
}: {
  apiBaseUrl: string;
  lastEvent: BackendEvent | null;
  audit: AuditEntry[];
  onSelectJob: (jobId: string) => void;
  events: FeedEvent[];
  connection: "connecting" | "connected" | "disconnected";
}) {
  const workItems = useKanbanStore((store) => store.items);
  const approvals = useApprovalStore((store) => store.entries);
  const pipelines = useDashboardStore((store) => store.pipelines);
  const openPullRequests = useDashboardStore((store) => store.openPullRequests);
  const versions = useDashboardStore((store) => store.versions);

  const passRate = overallPassRate(pipelines.value);
  const activityPoints = cumulativeActivity(audit);
  const runsPoints = auditRunsByDay(audit);
  const outcomeSlices = outcomeBreakdown(audit);

  return (
    <div className="overviewGrid">
      <div className="kpiRow">
        <KpiTile label="Active jobs" value={String(activeWorkItemsCount(workItems))} icon={Activity} tone="good" detail="Boards: Doing" />
        <KpiTile
          label="Open PRs"
          value={String(openPullRequests.value.length)}
          icon={GitPullRequest}
          tone="neutral"
          seeded={openPullRequests.source === "unavailable"}
        />
        <KpiTile
          label="Pipeline pass-rate"
          value={`${passRate}%`}
          icon={TrendingUp}
          tone={passRate >= 80 ? "good" : passRate >= 55 ? "warning" : "critical"}
          seeded={pipelines.source === "unavailable"}
        />
        <KpiTile
          label="Version posture"
          value={versionPostureLabel(versions.value)}
          icon={GitBranch}
          tone={versionsBehindCount(versions.value) === 0 ? "good" : "warning"}
          seeded={versions.source === "unavailable"}
        />
        <KpiTile label="Pending approvals" value={String(pendingApprovalsCount(approvals))} icon={ShieldCheck} tone={pendingApprovalsCount(approvals) > 0 ? "warning" : "good"} />
        <KpiTile
          label="Drift"
          value={String(versionsBehindCount(versions.value))}
          icon={Timer}
          tone={versionsBehindCount(versions.value) === 0 ? "good" : "warning"}
          detail="modules behind latest"
          seeded={versions.source === "unavailable"}
        />
      </div>

      <div className="overviewMainGrid">
        <GaugeCard label="Platform health" value={passRate} caption="pipeline pass-rate" />
        <ActivityLineCard points={activityPoints} />
        <RunsBarCard points={runsPoints} />
        <OutcomesDonutCard slices={outcomeSlices} />
        <AlertsFeed entries={audit} onSelectJob={onSelectJob} />
        <ModuleGraphCard />
        <ProvisioningCard lastEvent={lastEvent} />
        <section className="dashCard approvalOverviewCard" aria-labelledby="approvals-overview-heading">
          <header className="dashCardHeader">
            <h2 id="approvals-overview-heading">Approvals</h2>
          </header>
          {pendingApprovalsCount(approvals) === 0 && approvals.length === 0 ? (
            <p className="dashCardEmpty">No approval gates pending.</p>
          ) : (
            <ApprovalGate apiBaseUrl={apiBaseUrl} lastEvent={lastEvent} />
          )}
        </section>
        <EventFeedCard events={events} connection={connection} />
      </div>
    </div>
  );
}
