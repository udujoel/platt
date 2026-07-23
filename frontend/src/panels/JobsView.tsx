import React from "react";
import { ChevronDown, ChevronUp, Play, SendHorizonal } from "lucide-react";
import { MicButton } from "../voice/MicButton";
import type { PlanEntry } from "./provision-store";
import { JobInspector } from "./JobInspector";
import type { AsyncState, Job } from "./JobInspector";
import type { PersistedJobEvent } from "../job-event-description";

export type ChatMessage = {
  id: string;
  author: "operator" | "platt";
  text: string;
  jobId?: string;
  streaming?: boolean;
  createdAt: string;
};

function PlanBlock({ entry, onToggle }: { entry: PlanEntry; onToggle: () => void }) {
  return (
    <div className="message platt planBlock" key={entry.id}>
      <span>Platt · Plan</span>
      <button type="button" className="planBlockToggle" onClick={onToggle} aria-expanded={!entry.collapsed}>
        {entry.collapsed ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronUp size={14} aria-hidden="true" />}
        {entry.collapsed ? "Show plan" : "Hide plan"}
      </button>
      {entry.collapsed ? null : <pre className="planBlockBody">{entry.summary}</pre>}
    </div>
  );
}

export function JobsView({
  messages,
  planEntries,
  onTogglePlan,
  draft,
  onDraftChange,
  busy,
  onSubmit,
  onAutoSend,
  onStateCycle,
  selectedJobId,
  job,
  jobEvents,
  onRefreshJob,
}: {
  messages: ChatMessage[];
  planEntries: PlanEntry[];
  onTogglePlan: (id: string) => void;
  draft: string;
  onDraftChange: (value: string) => void;
  busy: boolean;
  onSubmit: (event: React.FormEvent<HTMLFormElement>) => void;
  onAutoSend: (text: string) => void;
  onStateCycle: () => void;
  selectedJobId: string | null;
  job: AsyncState<Job | null>;
  jobEvents: AsyncState<PersistedJobEvent[]>;
  onRefreshJob: () => void;
}) {
  const timeline: Array<{ key: string; createdAt: string; kind: "message" | "plan"; message?: ChatMessage; plan?: PlanEntry }> = [
    ...messages.map((message) => ({ key: `m-${message.id}`, createdAt: message.createdAt, kind: "message" as const, message })),
    ...planEntries.map((plan) => ({ key: `p-${plan.id}`, createdAt: plan.createdAt, kind: "plan" as const, plan })),
  ].sort((a, b) => a.createdAt.localeCompare(b.createdAt));

  return (
    <div className="jobsViewGrid">
      <section className="dashCard jobsChatCard" aria-labelledby="jobs-chat-heading">
        <header className="dashCardHeader">
          <h2 id="jobs-chat-heading">Chat with Platt</h2>
          <button className="cycleButton" type="button" onClick={onStateCycle} title="Run backend state cycle">
            <Play size={16} aria-hidden="true" />
          </button>
        </header>
        <div className="messageList jobsMessageList">
          {timeline.map((entry) =>
            entry.kind === "plan" && entry.plan ? (
              <PlanBlock key={entry.key} entry={entry.plan} onToggle={() => onTogglePlan(entry.plan!.id)} />
            ) : entry.message ? (
              <div className={`message ${entry.message.author}`} key={entry.key}>
                <span>{entry.message.author === "platt" ? "Platt" : "Operator"}</span>
                <p>
                  {entry.message.text}
                  {entry.message.streaming ? <b className="cursor">|</b> : null}
                </p>
              </div>
            ) : null,
          )}
        </div>
        <form className="composer" onSubmit={onSubmit}>
          <label htmlFor="chat-input">Message</label>
          <div>
            <input
              id="chat-input"
              value={draft}
              disabled={busy}
              onChange={(event) => onDraftChange(event.target.value)}
              placeholder="Send through backend /chat"
            />
            <MicButton disabled={busy} getDraft={() => draft} onDraftChange={onDraftChange} onAutoSend={onAutoSend} />
            <button type="submit" aria-label="Send message" title="Send message" disabled={busy}>
              <SendHorizonal size={18} aria-hidden="true" />
            </button>
          </div>
        </form>
      </section>
      <JobInspector selectedJobId={selectedJobId} job={job} jobEvents={jobEvents} onRefresh={onRefreshJob} />
    </div>
  );
}
