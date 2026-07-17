import React from "react";
import ReactDOM from "react-dom/client";
import { ChevronRight, CircleAlert, ClipboardList, Play, RefreshCw, SendHorizonal } from "lucide-react";
import { create } from "zustand";
import "./styles.css";

type PlattState =
  | "idle"
  | "listening"
  | "thinking"
  | "working"
  | "talking"
  | "awaiting_approval"
  | "celebrating"
  | "concerned";

type ConnectionState = "connecting" | "connected" | "disconnected";

type BackendEventType =
  | "agent_state"
  | "chat_delta"
  | "job_created"
  | "work_item_moved"
  | "pipeline_update"
  | "plan_ready"
  | "approval_required"
  | "approval_result"
  | "apply_result"
  | "audit_entry"
  | "dashboard_refresh";

type EventBase = {
  id: string;
  created_at: string;
};

type JobEvent = EventBase & {
  job_id?: string;
};

type BackendEvent =
  | (JobEvent & { type: "agent_state"; job_id: string; state: PlattState; label: string })
  | (JobEvent & { type: "chat_delta"; job_id: string; delta: string; index: number; done: boolean })
  | (JobEvent & { type: "job_created"; job_id: string; prompt: string })
  | (JobEvent & { type: "work_item_moved"; job_id: string; work_item_id: string; title: string; from_state: string; to_state: string })
  | (JobEvent & { type: "pipeline_update"; job_id: string; pipeline_name: string; status: string; url?: string | null })
  | (JobEvent & { type: "plan_ready"; job_id: string; summary: string; has_blocking_changes: boolean })
  | (JobEvent & { type: "approval_required"; job_id: string; approval_id: string; summary: string })
  | (JobEvent & { type: "approval_result"; job_id: string; approval_id: string; approved: boolean })
  | (JobEvent & { type: "apply_result"; job_id: string; success: boolean; summary: string })
  | (JobEvent & { type: "audit_entry"; job_id: string; tool: string; action: string; outcome: string })
  | (EventBase & { type: "dashboard_refresh"; metrics: Record<string, string | number> });

type EventEntry = {
  id: string;
  label: string;
  timestamp: string;
  state: PlattState;
};

type ChatMessage = {
  id: string;
  author: "operator" | "platt";
  text: string;
  jobId?: string;
  streaming?: boolean;
};

type AuditEntry = {
  id: number;
  job_id: string | null;
  tool: string;
  action: string;
  outcome: string;
  created_at: string;
};

type Job = {
  id: string;
  prompt: string;
  status: string;
  created_at: string;
  updated_at: string;
};

type PersistedJobEvent = {
  id: string;
  job_id: string;
  type: BackendEventType;
  payload: string;
  created_at: string;
};

type AsyncState<T> = {
  data: T;
  loading: boolean;
  error: string | null;
};

type EventStore = {
  state: PlattState;
  connection: ConnectionState;
  events: EventEntry[];
  messages: ChatMessage[];
  setConnection: (connection: ConnectionState) => void;
  applyBackendEvent: (event: BackendEvent) => void;
  addOperatorMessage: (text: string) => void;
  addLocalEvent: (state: PlattState, label: string) => void;
};

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const wsUrl = import.meta.env.VITE_WS_URL ?? "ws://127.0.0.1:8000/ws";

const stateLabels: Record<PlattState, string> = {
  idle: "Idle",
  listening: "Listening",
  thinking: "Thinking",
  working: "Working",
  talking: "Talking",
  awaiting_approval: "Awaiting Approval",
  celebrating: "Celebrating",
  concerned: "Concerned",
};

const createId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;
const formatTime = (value?: string) => (value ? new Date(value).toLocaleTimeString() : new Date().toLocaleTimeString());
const plattStates = new Set<PlattState>(["idle", "listening", "thinking", "working", "talking", "awaiting_approval", "celebrating", "concerned"]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasString(record: Record<string, unknown>, key: string): boolean {
  return typeof record[key] === "string";
}

function hasJobId(record: Record<string, unknown>): boolean {
  return hasString(record, "job_id");
}

function parseBackendEvent(value: unknown): BackendEvent | null {
  if (!isRecord(value) || !hasString(value, "id") || !hasString(value, "created_at") || !hasString(value, "type")) return null;

  switch (value.type) {
    case "agent_state":
      return hasJobId(value) && hasString(value, "label") && typeof value.state === "string" && plattStates.has(value.state as PlattState)
        ? (value as BackendEvent)
        : null;
    case "chat_delta":
      return hasJobId(value) && hasString(value, "delta") && Number.isInteger(value.index) && (value.index as number) >= 0 && typeof value.done === "boolean"
        ? (value as BackendEvent)
        : null;
    case "job_created":
      return hasJobId(value) && hasString(value, "prompt") ? (value as BackendEvent) : null;
    case "work_item_moved":
      return hasJobId(value) && ["work_item_id", "title", "from_state", "to_state"].every((key) => hasString(value, key)) ? (value as BackendEvent) : null;
    case "pipeline_update":
      return hasJobId(value) && hasString(value, "pipeline_name") && hasString(value, "status") && (value.url === undefined || value.url === null || typeof value.url === "string")
        ? (value as BackendEvent)
        : null;
    case "plan_ready":
      return hasJobId(value) && hasString(value, "summary") && typeof value.has_blocking_changes === "boolean" ? (value as BackendEvent) : null;
    case "approval_required":
      return hasJobId(value) && hasString(value, "approval_id") && hasString(value, "summary") ? (value as BackendEvent) : null;
    case "approval_result":
      return hasJobId(value) && hasString(value, "approval_id") && typeof value.approved === "boolean" ? (value as BackendEvent) : null;
    case "apply_result":
      return hasJobId(value) && typeof value.success === "boolean" && hasString(value, "summary") ? (value as BackendEvent) : null;
    case "audit_entry":
      return hasJobId(value) && ["tool", "action", "outcome"].every((key) => hasString(value, key)) ? (value as BackendEvent) : null;
    case "dashboard_refresh":
      return isRecord(value.metrics) && Object.values(value.metrics).every((metric) => typeof metric === "string" || typeof metric === "number") ? (value as BackendEvent) : null;
    default:
      return null;
  }
}

const useEventStore = create<EventStore>((set) => ({
  state: "idle",
  connection: "connecting",
  events: [
    {
      id: createId(),
      label: "Phase 1 shell mounted",
      timestamp: formatTime(),
      state: "idle",
    },
  ],
  messages: [
    {
      id: createId(),
      author: "platt",
      text: "Phase 1 interface ready. Connect the backend to stream live events.",
    },
  ],
  setConnection: (connection) =>
    set((current) => ({
      connection,
      events: [
        {
          id: createId(),
          label: connection === "connected" ? "WebSocket connected" : `WebSocket ${connection}`,
          timestamp: formatTime(),
          state: current.state,
        },
        ...current.events,
      ].slice(0, 10),
    })),
  addOperatorMessage: (text) =>
    set((current) => ({
      state: "listening",
      messages: [...current.messages, { id: createId(), author: "operator", text }],
      events: [
        {
          id: createId(),
          label: "Operator message sent",
          timestamp: formatTime(),
          state: "listening" as PlattState,
        },
        ...current.events,
      ].slice(0, 10),
    })),
  addLocalEvent: (state, label) =>
    set((current) => ({
      state,
      events: [{ id: createId(), label, timestamp: formatTime(), state }, ...current.events].slice(0, 10),
    })),
  applyBackendEvent: (event) =>
    set((current) => {
      if (event.type === "agent_state" && event.state && event.label) {
        return {
          state: event.state,
          events: [
            {
              id: event.id,
              label: event.label,
              timestamp: formatTime(event.created_at),
              state: event.state,
            },
            ...current.events,
          ].slice(0, 10),
        };
      }

      if (event.type === "job_created") {
        return {
          events: [
            {
              id: event.id,
              label: "Job accepted by backend",
              timestamp: formatTime(event.created_at),
              state: current.state,
            },
            ...current.events,
          ].slice(0, 10),
        };
      }

      if (event.type !== "chat_delta" || !event.job_id || event.delta === undefined) {
        return current;
      }

      const existingMessage = current.messages.find((message) => message.jobId === event.job_id);
      const nextMessages = existingMessage
        ? current.messages.map((message) =>
            message.jobId === event.job_id
              ? {
                  ...message,
                  text: `${message.text}${event.delta}`,
                  streaming: !event.done,
                }
              : message,
          )
        : [
            ...current.messages,
            {
              id: event.id,
              author: "platt" as const,
              text: event.delta,
              jobId: event.job_id,
              streaming: !event.done,
            },
          ];

      return { messages: nextMessages };
    }),
}));

function useBackendEvents() {
  const [lastEvent, setLastEvent] = React.useState<BackendEvent | null>(null);

  React.useEffect(() => {
    let closed = false;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;

    const connect = () => {
      useEventStore.getState().setConnection("connecting");
      socket = new WebSocket(wsUrl);

      socket.addEventListener("open", () => {
        useEventStore.getState().setConnection("connected");
      });

      socket.addEventListener("message", (message) => {
        try {
          const event = parseBackendEvent(JSON.parse(message.data) as unknown);
          if (!event) {
            useEventStore.getState().addLocalEvent("concerned", "Received an unsupported backend event");
            return;
          }
          useEventStore.getState().applyBackendEvent(event);
          setLastEvent(event);
        } catch {
          useEventStore.getState().addLocalEvent("concerned", "Received an unreadable backend event");
        }
      });

      socket.addEventListener("close", () => {
        if (closed) return;
        useEventStore.getState().setConnection("disconnected");
        retryTimer = window.setTimeout(connect, 2500);
      });

      socket.addEventListener("error", () => {
        socket?.close();
      });
    };

    connect();

    return () => {
      closed = true;
      window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, []);

  return lastEvent;
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, options);

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

async function postJson<T>(path: string, body?: unknown): Promise<T> {
  return requestJson<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

function PlattCharacter({ state, speech }: { state: PlattState; speech: string }) {
  const [bubbleVisible, setBubbleVisible] = React.useState(false);
  const hasSpoken = React.useRef(false);

  React.useEffect(() => {
    if (state === "talking" && speech) {
      hasSpoken.current = true;
      setBubbleVisible(true);
      return undefined;
    }
    if (!hasSpoken.current) return undefined;
    const hideTimer = window.setTimeout(() => setBubbleVisible(false), 4000);
    return () => window.clearTimeout(hideTimer);
  }, [speech, state]);

  return (
    <div className={`plattCharacter ${state}`} aria-label={`Platt is ${stateLabels[state].toLowerCase()}`}>
      <div className="confetti" aria-hidden="true"><i /><i /><i /><i /><i /></div>
      {bubbleVisible ? <div className="plattBubble">{speech.slice(-220)}</div> : null}
      {state === "thinking" ? <div className="thoughtDots" aria-label="Platt is thinking"><b /> <b /> <b /></div> : null}
      <div className="plattShadow" aria-hidden="true" />
      <div className="plattBody" aria-hidden="true">
        <div className="plattHead"><span className="ear left" /><span className="ear right" /><div className="hair" /><div className="face"><span className="eye left" /><span className="eye right" /><span className="nose" /><span className="mouth" /></div></div>
        <div className="plattNeck" /><div className="plattTorso"><span className="shirt" /><span className="lapel left" /><span className="lapel right" /></div>
        <div className="plattArm left"><span className="hand" /></div><div className="plattArm right"><span className="hand" /></div>
        <div className="plattLeg left"><span className="shoe" /></div><div className="plattLeg right"><span className="shoe" /></div>
      </div>
    </div>
  );
}

function OfficeScene({ state, speech }: { state: PlattState; speech: string }) {
  return <div className={`officeScene ${state}`}>
    <div className="wallBoard" aria-label="Miniature Kanban board"><span>PLATT BOARD</span><div><i /> <i /> <i /></div></div>
    <div className="serverRack" aria-label="Server rack"><i /><i /><i /><i /></div>
    <div className="desk"><div className="monitor"><span>PLATT</span><i /></div><div className="keyboard" /><div className="deskLeg left" /><div className="deskLeg right" /></div>
    <div className="plant"><i /><i /><i /><b /></div><div className="pebble" aria-hidden="true" /><PlattCharacter state={state} speech={speech} /><div className="floorGrid" aria-hidden="true" />
  </div>;
}

function Stage() {
  const state = useEventStore((store) => store.state);
  const connection = useEventStore((store) => store.connection);
  const messages = useEventStore((store) => store.messages);
  const latestPlattMessage = [...messages].reverse().find((message) => message.author === "platt")?.text ?? "";

  return (
    <section className="stage" aria-label="Platt office stage">
      <div className="stageHeader">
        <StatusChip state={state} />
        <span className={`connectionBadge ${connection}`}>{connection}</span>
      </div>
      <OfficeScene state={state} speech={latestPlattMessage} />
      <div className="stageFooter">
        <span>Platt · embodied DevOps agent</span>
        <span>Live event projection</span>
      </div>
    </section>
  );
}

function StatusChip({ state }: { state: PlattState }) {
  return (
    <div className={`statusChip ${state}`} aria-live="polite">
      <span className="statusDot" />
      {stateLabels[state]}
    </div>
  );
}

const initialAuditState: AsyncState<AuditEntry[]> = { data: [], loading: true, error: null };
const initialJobState: AsyncState<Job | null> = { data: null, loading: false, error: null };
const initialJobEventsState: AsyncState<PersistedJobEvent[]> = { data: [], loading: false, error: null };

function formatDateTime(value: string) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Unknown time" : date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function describePersistedEvent(event: PersistedJobEvent) {
  let payload: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(event.payload);
    if (!isRecord(parsed)) throw new Error("Invalid event payload");
    payload = parsed;
  } catch {
    return { title: event.type.replace(/_/g, " "), detail: "Event payload could not be read." };
  }

  switch (event.type) {
    case "agent_state":
      return { title: String(payload.label ?? "Agent state changed"), detail: String(payload.state ?? "state") };
    case "chat_delta":
      return { title: payload.done ? "Response complete" : "Response streamed", detail: String(payload.delta ?? "") || "No visible text" };
    case "job_created":
      return { title: "Job accepted", detail: String(payload.prompt ?? "") };
    case "work_item_moved":
      return { title: String(payload.title ?? "Work item moved"), detail: `${String(payload.from_state ?? "Unknown")} → ${String(payload.to_state ?? "Unknown")}` };
    case "pipeline_update":
      return { title: String(payload.pipeline_name ?? "Pipeline updated"), detail: String(payload.status ?? "Unknown") };
    case "plan_ready":
    case "apply_result":
      return { title: event.type === "plan_ready" ? "Plan ready" : "Apply result", detail: String(payload.summary ?? "") };
    case "approval_required":
      return { title: "Approval required", detail: String(payload.summary ?? "") };
    case "approval_result":
      return { title: "Approval recorded", detail: payload.approved ? "Approved" : "Not approved" };
    case "audit_entry":
      return { title: `${String(payload.tool ?? "Tool")} · ${String(payload.action ?? "action")}`, detail: String(payload.outcome ?? "") };
    default:
      return { title: event.type.replace(/_/g, " "), detail: "Backend event recorded" };
  }
}

function AuditInspector({
  selectedJobId,
  onSelectJob,
  lastEvent,
}: {
  selectedJobId: string | null;
  onSelectJob: (jobId: string) => void;
  lastEvent: BackendEvent | null;
}) {
  const [audit, setAudit] = React.useState<AsyncState<AuditEntry[]>>(initialAuditState);
  const [job, setJob] = React.useState<AsyncState<Job | null>>(initialJobState);
  const [jobEvents, setJobEvents] = React.useState<AsyncState<PersistedJobEvent[]>>(initialJobEventsState);
  const auditRequestId = React.useRef(0);
  const jobRequestId = React.useRef(0);

  const refreshAudit = React.useCallback(async (showLoading = false) => {
    const requestId = ++auditRequestId.current;
    if (showLoading) setAudit((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await requestJson<{ entries: AuditEntry[] }>("/audit");
      if (requestId !== auditRequestId.current) return;
      setAudit({ data: response.entries, loading: false, error: null });
    } catch {
      if (requestId !== auditRequestId.current) return;
      setAudit((current) => ({ ...current, loading: false, error: "Could not load the audit trail." }));
    }
  }, []);

  const refreshJob = React.useCallback(async (jobId: string) => {
    const requestId = ++jobRequestId.current;
    setJob({ data: null, loading: true, error: null });
    setJobEvents({ data: [], loading: true, error: null });
    const [jobResult, eventsResult] = await Promise.allSettled([
        requestJson<Job>(`/jobs/${encodeURIComponent(jobId)}`),
        requestJson<{ events: PersistedJobEvent[] }>(`/jobs/${encodeURIComponent(jobId)}/events`),
    ]);
    if (requestId !== jobRequestId.current) return;

    if (jobResult.status === "fulfilled") {
      setJob({ data: jobResult.value, loading: false, error: null });
    } else {
      setJob({ data: null, loading: false, error: "This job is no longer available." });
    }
    if (eventsResult.status === "fulfilled") {
      setJobEvents({ data: eventsResult.value.events, loading: false, error: null });
    } else {
      setJobEvents({ data: [], loading: false, error: "Could not load this job's events." });
    }
  }, []);

  React.useEffect(() => {
    void refreshAudit(true);
  }, [refreshAudit]);

  React.useEffect(() => {
    if (!selectedJobId) {
      jobRequestId.current += 1;
      setJob(initialJobState);
      setJobEvents(initialJobEventsState);
      return;
    }
    void refreshJob(selectedJobId);
  }, [refreshJob, selectedJobId]);

  React.useEffect(() => {
    if (!lastEvent) return;
    if (lastEvent.type === "job_created" || lastEvent.type === "audit_entry") {
      void refreshAudit();
    }
    if (lastEvent.type === "job_created") {
      if (!selectedJobId && lastEvent.job_id) onSelectJob(lastEvent.job_id);
    }
    if (!("job_id" in lastEvent) || lastEvent.job_id !== selectedJobId || !selectedJobId) return;
    const delay = lastEvent.type === "chat_delta" ? 300 : 0;
    const refreshTimer = window.setTimeout(() => void refreshJob(selectedJobId), delay);
    return () => window.clearTimeout(refreshTimer);
  }, [lastEvent, onSelectJob, refreshAudit, refreshJob, selectedJobId]);

  return (
    <aside className="auditPanel" aria-label="Audit and job inspector">
      <section className="auditSection auditListSection" aria-labelledby="audit-heading">
        <header className="auditHeader">
          <div>
            <p className="eyebrow">Observability</p>
            <h1 id="audit-heading">Audit trail</h1>
          </div>
          <button
            className="iconButton"
            type="button"
            onClick={() => void refreshAudit(true)}
            disabled={audit.loading}
            aria-label="Refresh audit trail"
            title="Refresh audit trail"
          >
            <RefreshCw size={15} className={audit.loading ? "spinning" : undefined} aria-hidden="true" />
          </button>
        </header>

        {audit.error ? (
          <LoadError message={audit.error} onRetry={() => void refreshAudit(true)} />
        ) : audit.loading && audit.data.length === 0 ? (
          <AuditSkeleton />
        ) : audit.data.length === 0 ? (
          <EmptyState title="No audit entries yet" detail="New jobs and tool activity will appear here." />
        ) : (
          <ol className="auditList">
            {audit.data.map((entry) => {
              const selectable = Boolean(entry.job_id);
              return (
                <li key={entry.id}>
                  <button
                    className={`auditItem ${selectedJobId === entry.job_id ? "selected" : ""}`}
                    type="button"
                    onClick={() => entry.job_id && onSelectJob(entry.job_id)}
                    disabled={!selectable}
                    aria-current={selectedJobId === entry.job_id ? "true" : undefined}
                  >
                    <span className="auditItemTop"><strong>{entry.tool}</strong><time dateTime={entry.created_at}>{formatDateTime(entry.created_at)}</time></span>
                    <span className="auditAction">{entry.action.replace(/_/g, " ")}</span>
                    <span className="auditOutcome">{entry.outcome}</span>
                    {selectable ? <ChevronRight size={15} aria-hidden="true" /> : null}
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </section>

      <section className="auditSection jobInspector" aria-labelledby="job-heading">
        <header>
          <div>
            <p className="eyebrow">Selected job</p>
            <h2 id="job-heading">Job inspector</h2>
          </div>
          {selectedJobId ? (
            <button className="textButton" type="button" onClick={() => void refreshJob(selectedJobId)}>
              Refresh
            </button>
          ) : null}
        </header>

        {!selectedJobId ? (
          <EmptyState title="Select an audit entry" detail="Choose an entry associated with a job to inspect its request and event history." />
        ) : job.loading ? (
          <JobSkeleton />
        ) : job.error ? (
          <LoadError message={job.error} onRetry={() => void refreshJob(selectedJobId)} />
        ) : job.data ? (
          <>
            <dl className="jobDetails">
              <div><dt>Status</dt><dd className="jobStatus">{job.data.status}</dd></div>
              <div><dt>Created</dt><dd>{formatDateTime(job.data.created_at)}</dd></div>
              <div className="jobPrompt"><dt>Request</dt><dd>{job.data.prompt}</dd></div>
              <div className="jobIdentifier"><dt>Job ID</dt><dd title={job.data.id}>{job.data.id}</dd></div>
            </dl>

            <div className="jobEventHeader"><h3>Event history</h3><span>{jobEvents.data.length}</span></div>
            {jobEvents.loading ? (
              <JobEventSkeleton />
            ) : jobEvents.error ? (
              <LoadError message={jobEvents.error} onRetry={() => void refreshJob(selectedJobId)} />
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
    </aside>
  );
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="emptyState"><ClipboardList size={18} aria-hidden="true" /><strong>{title}</strong><p>{detail}</p></div>;
}

function LoadError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div className="loadError" role="alert"><CircleAlert size={18} aria-hidden="true" /><p>{message}</p><button className="textButton" type="button" onClick={onRetry}>Try again</button></div>;
}

function AuditSkeleton() {
  return <div className="skeletonStack" aria-label="Loading audit entries"><span /><span /><span /></div>;
}

function JobSkeleton() {
  return <div className="skeletonStack jobSkeleton" aria-label="Loading job details"><span /><span /><span /><span /></div>;
}

function JobEventSkeleton() {
  return <div className="skeletonStack eventSkeleton" aria-label="Loading job events"><span /><span /></div>;
}

function ChatPanel({ onJobAccepted }: { onJobAccepted: (jobId: string) => void }) {
  const messages = useEventStore((store) => store.messages);
  const events = useEventStore((store) => store.events);
  const addOperatorMessage = useEventStore((store) => store.addOperatorMessage);
  const addLocalEvent = useEventStore((store) => store.addLocalEvent);
  const [draft, setDraft] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text || busy) return;

    setBusy(true);
    addOperatorMessage(text);
    setDraft("");

    try {
      const response = await postJson<{ job_id: string }>("/chat", { prompt: text });
      onJobAccepted(response.job_id);
    } catch {
      addLocalEvent("concerned", "Backend chat request failed");
    } finally {
      setBusy(false);
    }
  };

  const runStateCycle = async () => {
    try {
      await postJson("/dev/state-cycle");
    } catch {
      addLocalEvent("concerned", "Backend state cycle request failed");
    }
  };

  return (
    <aside className="chatPanel" aria-label="Chat and event timeline">
      <div className="panelSection messages">
        <header>
          <div>
            <h1>Platt</h1>
            <p>Phase 1 event contract</p>
          </div>
          <button className="cycleButton" type="button" onClick={runStateCycle} title="Run backend state cycle">
            <Play size={16} aria-hidden="true" />
          </button>
        </header>
        <div className="messageList">
          {messages.map((message) => (
            <div className={`message ${message.author}`} key={message.id}>
              <span>{message.author === "platt" ? "Platt" : "Operator"}</span>
              <p>
                {message.text}
                {message.streaming ? <b className="cursor">|</b> : null}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="panelSection events">
        <h2>Event Store</h2>
        <ol>
          {events.map((event) => (
            <li key={event.id}>
              <span>{event.timestamp}</span>
              <strong>{stateLabels[event.state]}</strong>
              <p>{event.label}</p>
            </li>
          ))}
        </ol>
      </div>

      <form className="composer" onSubmit={onSubmit}>
        <label htmlFor="chat-input">Message</label>
        <div>
          <input
            id="chat-input"
            value={draft}
            disabled={busy}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Send through backend /chat"
          />
          <button type="submit" aria-label="Send message" title="Send message" disabled={busy}>
            <SendHorizonal size={18} aria-hidden="true" />
          </button>
        </div>
      </form>
    </aside>
  );
}

function App() {
  const lastEvent = useBackendEvents();
  const [selectedJobId, setSelectedJobId] = React.useState<string | null>(null);
  const selectJob = React.useCallback((jobId: string) => setSelectedJobId(jobId), []);

  return (
    <main className="appShell">
      <AuditInspector selectedJobId={selectedJobId} onSelectJob={selectJob} lastEvent={lastEvent} />
      <Stage />
      <ChatPanel onJobAccepted={selectJob} />
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
