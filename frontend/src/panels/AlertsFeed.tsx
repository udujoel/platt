import React from "react";
import { AlertTriangle, CircleAlert, Info } from "lucide-react";
import { classifyAuditSeverity } from "./dashboard-metrics";
import type { AuditEntry } from "./dashboard-metrics";

function formatTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

const severityIcon = { info: Info, warning: AlertTriangle, critical: CircleAlert } as const;

export function AlertsFeed({
  entries,
  onSelectJob,
  limit = 6,
}: {
  entries: AuditEntry[];
  onSelectJob?: (jobId: string) => void;
  limit?: number;
}) {
  const recent = entries.slice(0, limit);

  return (
    <section className="dashCard alertsFeedCard" aria-labelledby="alerts-heading">
      <header className="dashCardHeader">
        <h2 id="alerts-heading">Recent alerts &amp; audit</h2>
        <span className="dashCardSubtitle">{entries.length} total</span>
      </header>
      {recent.length === 0 ? (
        <p className="dashCardEmpty">No audit activity yet.</p>
      ) : (
        <ol className="alertsFeedList">
          {recent.map((entry) => {
            const severity = classifyAuditSeverity(entry.outcome);
            const Icon = severityIcon[severity];
            const clickable = Boolean(entry.job_id && onSelectJob);
            const Tag = clickable ? "button" : "div";
            return (
              <li key={entry.id}>
                <Tag
                  type={clickable ? "button" : undefined}
                  className={`alertsFeedItem sev-${severity}`}
                  onClick={clickable ? () => onSelectJob?.(entry.job_id as string) : undefined}
                >
                  <Icon size={14} aria-hidden="true" />
                  <div>
                    <strong>{entry.tool} · {entry.action.replace(/_/g, " ")}</strong>
                    <p>{entry.outcome}</p>
                  </div>
                  <time dateTime={entry.created_at}>{formatTime(entry.created_at)}</time>
                </Tag>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
