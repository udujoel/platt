import React from "react";
import ReactDOM from "react-dom/client";
import { ChevronRight, CircleAlert, ClipboardList, Play, RefreshCw, SendHorizonal } from "lucide-react";
import { Canvas, useFrame } from "@react-three/fiber";
import type { Mesh } from "three";
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

type BackendEvent = {
  id: string;
  type: BackendEventType;
  created_at: string;
  job_id?: string;
  state?: PlattState;
  label?: string;
  delta?: string;
  index?: number;
  done?: boolean;
};

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
          const event = JSON.parse(message.data) as BackendEvent;
          if (!event.id || !event.type || !event.created_at) return;
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

function PlattCapsule() {
  const mesh = React.useRef<Mesh>(null);
  const state = useEventStore((store) => store.state);

  useFrame(({ clock }) => {
    if (!mesh.current) return;
    const elapsed = clock.getElapsedTime();
    mesh.current.rotation.y = elapsed * 0.35;
    mesh.current.position.y = Math.sin(elapsed * 1.4) * 0.08;
  });

  const color =
    state === "concerned"
      ? "#f87171"
      : state === "celebrating"
        ? "#2dd4bf"
        : state === "thinking" || state === "working"
          ? "#ffb454"
          : "#8bb8ff";

  return (
    <group>
      <mesh ref={mesh} castShadow receiveShadow>
        <capsuleGeometry args={[0.72, 2.25, 16, 32]} />
        <meshStandardMaterial color={color} metalness={0.28} roughness={0.36} />
      </mesh>
      <mesh position={[0, -1.72, 0]} rotation={[-Math.PI / 2, 0, 0]} receiveShadow>
        <circleGeometry args={[1.2, 48]} />
        <meshBasicMaterial color="#1f2937" transparent opacity={0.26} />
      </mesh>
    </group>
  );
}

function Stage() {
  const state = useEventStore((store) => store.state);
  const connection = useEventStore((store) => store.connection);

  return (
    <section className="stage" aria-label="Platt avatar stage">
      <div className="stageHeader">
        <StatusChip state={state} />
        <span className={`connectionBadge ${connection}`}>{connection}</span>
      </div>
      <Canvas camera={{ position: [0, 0.4, 5], fov: 42 }} dpr={[1, 1.5]} shadows>
        <color attach="background" args={["#10131a"]} />
        <ambientLight intensity={0.45} />
        <directionalLight position={[3, 4, 5]} intensity={1.7} castShadow />
        <pointLight position={[-3, -1, 2]} intensity={1.2} color="#2dd4bf" />
        <PlattCapsule />
      </Canvas>
      <div className="stageFooter">
        <span>Platt capsule placeholder</span>
        <span>Backend event contract</span>
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
    payload = JSON.parse(event.payload) as Record<string, unknown>;
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
  const jobRequestId = React.useRef(0);

  const refreshAudit = React.useCallback(async (showLoading = false) => {
    if (showLoading) setAudit((current) => ({ ...current, loading: true, error: null }));
    try {
      const response = await requestJson<{ entries: AuditEntry[] }>("/audit");
      setAudit({ data: response.entries, loading: false, error: null });
    } catch {
      setAudit((current) => ({ ...current, loading: false, error: "Could not load the audit trail." }));
    }
  }, []);

  const refreshJob = React.useCallback(async (jobId: string) => {
    const requestId = ++jobRequestId.current;
    setJob({ data: null, loading: true, error: null });
    setJobEvents({ data: [], loading: true, error: null });
    try {
      const [nextJob, eventsResponse] = await Promise.all([
        requestJson<Job>(`/jobs/${encodeURIComponent(jobId)}`),
        requestJson<{ events: PersistedJobEvent[] }>(`/jobs/${encodeURIComponent(jobId)}/events`),
      ]);
      if (requestId !== jobRequestId.current) return;
      setJob({ data: nextJob, loading: false, error: null });
      setJobEvents({ data: eventsResponse.events, loading: false, error: null });
    } catch {
      if (requestId !== jobRequestId.current) return;
      setJob({ data: null, loading: false, error: "This job is no longer available." });
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
    if (lastEvent.type === "job_created") {
      void refreshAudit();
      if (!selectedJobId && lastEvent.job_id) onSelectJob(lastEvent.job_id);
    }
    if (lastEvent.job_id !== selectedJobId || !selectedJobId) return;
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
