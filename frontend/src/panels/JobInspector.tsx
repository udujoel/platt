import React from "react";
import { describePersistedEvent } from "../job-event-description";
import type { PersistedJobEvent } from "../job-event-description";

export type Job = { id: string; prompt: string; status: string; created_at: string; updated_at: string };
export type AsyncState<T> = { data: T; loading: boolean; error: string | null };

function formatDateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown time" : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

export function EmptyState({ title, detail, icon }: { title: string; detail: string; icon?: React.ReactNode }) {
  return (
    <div className="emptyState">
      {icon}
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  );
}

export function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="loadError" role="alert">
      <p>{message}</p>
      <button className="textButton" type="button" onClick={onRetry}>
        Try again
      </button>
    </div>
  );
}

export function JobInspector({
  selectedJobId,
  job,
  jobEvents,
  onRefresh,
}: {
  selectedJobId: string | null;
  job: AsyncState<Job | null>;
  jobEvents: AsyncState<PersistedJobEvent[]>;
  onRefresh: () => void;
}) {
  return (
    <section className="dashCard jobInspectorCard" aria-labelledby="job-inspector-heading">
      <header className="dashCardHeader">
        <h2 id="job-inspector-heading">Job inspector</h2>
        {selectedJobId ? (
          <button className="textButton" type="button" onClick={onRefresh}>
            Refresh
          </button>
        ) : null}
      </header>

      {!selectedJobId ? (
        <EmptyState title="Select a job" detail="Choose an audit entry or job to inspect its request and event history." />
      ) : job.loading ? (
        <div className="skeletonStack jobSkeleton" aria-label="Loading job details"><span /><span /><span /></div>
      ) : job.error ? (
        <LoadError message={job.error} onRetry={onRefresh} />
      ) : job.data ? (
        <>
          <dl className="jobDetails">
            <div><dt>Status</dt><dd className="jobStatus">{job.data.status}</dd></div>
            <div><dt>Created</dt><dd>{formatDateTime(job.data.created_at)}</dd></div>
            <div className="jobPrompt"><dt>Request</dt><dd>{job.data.prompt}</dd></div>
            <div className="jobIdentifier"><dt>Job ID</dt><dd title={job.data.id}>{job.data.id}</dd></div>
          </dl>

          <div className="jobEventHeader">
            <h3>Event history</h3>
            <span>{jobEvents.data.length}</span>
          </div>
          {jobEvents.loading ? (
            <div className="skeletonStack eventSkeleton" aria-label="Loading job events"><span /><span /></div>
          ) : jobEvents.error ? (
            <LoadError message={jobEvents.error} onRetry={onRefresh} />
          ) : jobEvents.data.length === 0 ? (
            <EmptyState title="No saved events" detail="Events will be recorded as this job progresses." />
          ) : (
            <ol className="jobEventList">
              {jobEvents.data.map((event) => {
                const description = describePersistedEvent(event);
                return (
                  <li key={event.id}>
                    <time dateTime={event.created_at}>{formatDateTime(event.created_at)}</time>
                    <div><strong>{description.title}</strong><p>{description.detail}</p></div>
                  </li>
                );
              })}
            </ol>
          )}
        </>
      ) : null}
    </section>
  );
}
