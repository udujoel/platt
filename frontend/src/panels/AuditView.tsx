import React from "react";
import { RefreshCw } from "lucide-react";
import { classifyAuditSeverity } from "./dashboard-metrics";
import type { AuditEntry } from "./dashboard-metrics";
import { EmptyState, JobInspector, LoadError } from "./JobInspector";
import type { AsyncState, Job } from "./JobInspector";
import type { PersistedJobEvent } from "../job-event-description";

function formatDateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown time" : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export function AuditView({
  audit,
  onRefreshAudit,
  selectedJobId,
  onSelectJob,
  job,
  jobEvents,
  onRefreshJob,
}: {
  audit: AsyncState<AuditEntry[]>;
  onRefreshAudit: () => void;
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
  job: AsyncState<Job | null>;
  jobEvents: AsyncState<PersistedJobEvent[]>;
  onRefreshJob: () => void;
}) {
  return (
    <div className="auditViewGrid">
      <section className="dashCard auditTrailCard" aria-labelledby="audit-trail-heading">
        <header className="dashCardHeader">
          <h2 id="audit-trail-heading">Audit trail</h2>
          <button
            className="iconButton"
            type="button"
            onClick={onRefreshAudit}
            disabled={audit.loading}
            aria-label="Refresh audit trail"
            title="Refresh audit trail"
          >
            <RefreshCw size={15} className={audit.loading ? "spinning" : undefined} aria-hidden="true" />
          </button>
        </header>

        {audit.error ? (
          <LoadError message={audit.error} onRetry={onRefreshAudit} />
        ) : audit.loading && audit.data.length === 0 ? (
          <div className="skeletonStack" aria-label="Loading audit entries"><span /><span /><span /></div>
        ) : audit.data.length === 0 ? (
          <EmptyState title="No audit entries yet" detail="New jobs and tool activity will appear here." />
        ) : (
          <ol className="auditList">
            {audit.data.map((entry) => {
              const selectable = Boolean(entry.job_id);
              const severity = classifyAuditSeverity(entry.outcome);
              return (
                <li key={entry.id}>
                  <button
                    className={`auditItem sev-${severity} ${selectedJobId === entry.job_id ? "selected" : ""}`}
                    type="button"
                    onClick={() => entry.job_id && onSelectJob(entry.job_id)}
                    disabled={!selectable}
                    aria-current={selectedJobId === entry.job_id ? "true" : undefined}
                  >
                    <span className="auditItemTop"><strong>{entry.tool}</strong><time dateTime={entry.created_at}>{formatDateTime(entry.created_at)}</time></span>
                    <span className="auditAction">{entry.action.replace(/_/g, " ")}</span>
                    <span className="auditOutcome">{entry.outcome}</span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </section>
      <JobInspector selectedJobId={selectedJobId} job={job} jobEvents={jobEvents} onRefresh={onRefreshJob} />
    </div>
  );
}
