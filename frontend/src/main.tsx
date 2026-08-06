import React from "react";
import ReactDOM from "react-dom/client";
import { CircleAlert } from "lucide-react";
import { create } from "zustand";
import "./styles.css";
import { resolveBackendConfiguration } from "./backend-config";
import type { BackendConfiguration } from "./backend-config";
import { createBackendReadinessPoller } from "./readiness-status";
import type { BackendReadiness } from "./readiness-status";
import { parseBackendEvent } from "./backend-events";
import type { BackendEvent, PlattState } from "./backend-events";
import { createSseClient } from "./sse-client";
import type { PersistedJobEvent } from "./job-event-description";
import { Sidebar } from "./panels/Sidebar";
import type { NavKey } from "./panels/Sidebar";
import { TopBar, navTitles } from "./panels/TopBar";
import { OverviewView } from "./panels/OverviewView";
import { JobsView } from "./panels/JobsView";
import type { ChatMessage } from "./panels/JobsView";
import { ProvisioningView } from "./panels/ProvisioningView";
import { PipelinesView } from "./panels/PipelinesView";
import { ModuleGraphCard } from "./panels/ModuleGraphCard";
import { BoardsBoard } from "./panels/BoardsBoard";
import { AuditView } from "./panels/AuditView";
import { ApprovalsView } from "./panels/ApprovalsView";
import { SettingsView } from "./panels/SettingsView";
import type { AsyncState, Job } from "./panels/JobInspector";
import { alertEntryCount } from "./panels/dashboard-metrics";
import type { AuditEntry } from "./panels/dashboard-metrics";
import type { OnboardingRecord } from "./panels/RepositoryPanel";
import { deriveProvisionSteps, provisionStatusLabel, useProvisionStore } from "./panels/provision-store";
import { useApprovalStore } from "./panels/approval-store";
import { useKanbanStore } from "./panels/kanban-store";
import { DASHBOARD_REFRESH_INTERVAL_MS, useDashboardStore } from "./panels/dashboard-store";
import { useVoiceMuteStore } from "./voice/mute-store";
import { useSpeechSynthesis } from "./voice/use-speech-synthesis";

const PlattDeskWidget = React.lazy(() => import("./scene/PlattDeskWidget"));

class DeskWidgetBoundary extends React.Component<{ children: React.ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? null : this.props.children;
  }
}

type ConnectionState = "connecting" | "connected" | "disconnected";

type EventEntry = { id: string; label: string; timestamp: string; state: PlattState };

type EventStore = {
  state: PlattState;
  connection: ConnectionState;
  events: EventEntry[];
  messages: ChatMessage[];
  seenBackendEventIds: string[];
  setConnection: (connection: ConnectionState) => void;
  applyBackendEvent: (event: BackendEvent) => void;
  addOperatorMessage: (text: string) => void;
  addLocalEvent: (state: PlattState, label: string) => void;
};

const backendConfiguration = resolveBackendConfiguration({
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL,
  frontendHostname: window.location.hostname,
  wsUrl: import.meta.env.VITE_WS_URL,
});
const { apiBaseUrl } = backendConfiguration;

const createId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;
const formatTime = (value?: string) => (value ? new Date(value).toLocaleTimeString() : new Date().toLocaleTimeString());
const nowIso = () => new Date().toISOString();

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

const useEventStore = create<EventStore>((set) => ({
  state: "idle",
  connection: "connecting",
  events: [
    { id: createId(), label: "Dashboard shell mounted", timestamp: formatTime(), state: "idle" },
  ],
  messages: [
    { id: createId(), author: "platt", text: "Dashboard ready. Connect the backend to stream live events.", createdAt: nowIso() },
  ],
  seenBackendEventIds: [],
  setConnection: (connection) =>
    set((current) => ({
      connection,
      events: [
        { id: createId(), label: connection === "connected" ? "Live stream connected" : `Live stream ${connection}`, timestamp: formatTime(), state: current.state },
        ...current.events,
      ].slice(0, 12),
    })),
  addOperatorMessage: (text) =>
    set((current) => ({
      state: "listening",
      messages: [...current.messages, { id: createId(), author: "operator", text, createdAt: nowIso() }],
      events: [
        { id: createId(), label: "Operator message sent", timestamp: formatTime(), state: "listening" as PlattState },
        ...current.events,
      ].slice(0, 12),
    })),
  addLocalEvent: (state, label) =>
    set((current) => ({
      state,
      events: [{ id: createId(), label, timestamp: formatTime(), state }, ...current.events].slice(0, 12),
    })),
  applyBackendEvent: (event) =>
    set((current) => {
      if (current.seenBackendEventIds.includes(event.id)) return current;
      const seenBackendEventIds = [...current.seenBackendEventIds, event.id].slice(-200);

      if (event.type === "agent_state" && event.state && event.label) {
        return {
          seenBackendEventIds,
          state: event.state,
          events: [
            { id: event.id, label: event.label, timestamp: formatTime(event.created_at), state: event.state },
            ...current.events,
          ].slice(0, 12),
        };
      }

      if (event.type === "job_created") {
        return {
          seenBackendEventIds,
          events: [
            { id: event.id, label: "Job accepted by backend", timestamp: formatTime(event.created_at), state: current.state },
            ...current.events,
          ].slice(0, 12),
        };
      }

      if (event.type !== "chat_delta" || !event.job_id || event.delta === undefined) {
        return { seenBackendEventIds };
      }

      const existingMessage = current.messages.find((message) => message.jobId === event.job_id);
      const nextMessages = existingMessage
        ? current.messages.map((message) =>
            message.jobId === event.job_id ? { ...message, text: `${message.text}${event.delta}`, streaming: !event.done } : message,
          )
        : [
            ...current.messages,
            { id: event.id, author: "platt" as const, text: event.delta, jobId: event.job_id, streaming: !event.done, createdAt: event.created_at },
          ];

      return { seenBackendEventIds, messages: nextMessages };
    }),
}));

function useBackendEvents() {
  const [lastEvent, setLastEvent] = React.useState<BackendEvent | null>(null);

  React.useEffect(() => {
    let closed = false;

    const deliver = (event: BackendEvent) => {
      const store = useEventStore.getState();
      if (store.seenBackendEventIds.includes(event.id)) return;
      store.applyBackendEvent(event);
      setLastEvent(event);
    };

    const hydrateOnMount = async () => {
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 5_000);
      try {
        const response = await requestJson<{ events: unknown[] }>("/events/recent?limit=100", { signal: controller.signal });
        for (const value of response.events) {
          const event = parseBackendEvent(value);
          if (event && !closed) deliver(event);
        }
      } catch {
        if (!closed) useEventStore.getState().addLocalEvent("concerned", "Could not recover persisted events on load");
      } finally {
        window.clearTimeout(timer);
      }
    };

    void hydrateOnMount();

    const client = createSseClient({
      streamUrl: () => `${apiBaseUrl}/events/stream`,
      onEvent: deliver,
      onConnectionChange: (connection) => useEventStore.getState().setConnection(connection),
      onUnparsableFrame: () => useEventStore.getState().addLocalEvent("concerned", "Received an unsupported backend event"),
    });
    client.start();

    return () => {
      closed = true;
      client.close();
    };
  }, []);

  return lastEvent;
}

function useBackendReadiness(): BackendReadiness {
  const [readiness, setReadiness] = React.useState<BackendReadiness>("checking");

  React.useEffect(() => {
    const poller = createBackendReadinessPoller({
      requestReadiness: (signal) => requestJson<unknown>("/ready", { signal }),
      onReadiness: setReadiness,
    });

    poller.start();
    return () => poller.stop();
  }, []);

  return readiness;
}

async function requestJson<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, options);

  if (!response.ok) {
    let detail = "";
    try {
      const payload: unknown = await response.json();
      if (isRecord(payload) && typeof payload.detail === "string") detail = payload.detail;
    } catch {
      // Keep the HTTP status as the actionable fallback when an error has no JSON body.
    }
    throw new Error(detail || `Request failed: ${response.status}`);
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

const initialAuditState: AsyncState<AuditEntry[]> = { data: [], loading: true, error: null };
const initialJobState: AsyncState<Job | null> = { data: null, loading: false, error: null };
const initialJobEventsState: AsyncState<PersistedJobEvent[]> = { data: [], loading: false, error: null };

/** Shared audit-trail + job-inspector fetch state, consumed by both the Overview alerts feed and the Audit/Jobs nav pages. */
function useAuditAndJobInspector(lastEvent: BackendEvent | null) {
  const [audit, setAudit] = React.useState<AsyncState<AuditEntry[]>>(initialAuditState);
  const [job, setJob] = React.useState<AsyncState<Job | null>>(initialJobState);
  const [jobEvents, setJobEvents] = React.useState<AsyncState<PersistedJobEvent[]>>(initialJobEventsState);
  const [selectedJobId, setSelectedJobId] = React.useState<string | null>(null);
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

  const selectJob = React.useCallback((jobId: string) => setSelectedJobId(jobId), []);

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
      if (!selectedJobId && lastEvent.job_id) selectJob(lastEvent.job_id);
    }
    if (!("job_id" in lastEvent) || lastEvent.job_id !== selectedJobId || !selectedJobId) return;
    const delay = lastEvent.type === "chat_delta" ? 300 : 0;
    const refreshTimer = window.setTimeout(() => void refreshJob(selectedJobId), delay);
    return () => window.clearTimeout(refreshTimer);
  }, [lastEvent, refreshAudit, refreshJob, selectJob, selectedJobId]);

  return { audit, refreshAudit: () => void refreshAudit(true), job, jobEvents, selectedJobId, selectJob, refreshJob: () => selectedJobId && void refreshJob(selectedJobId) };
}

function DashboardShell({ readiness, lastEvent }: { readiness: BackendReadiness; lastEvent: BackendEvent | null }) {
  const state = useEventStore((store) => store.state);
  const connection = useEventStore((store) => store.connection);
  const messages = useEventStore((store) => store.messages);
  const events = useEventStore((store) => store.events);
  const addOperatorMessage = useEventStore((store) => store.addOperatorMessage);
  const addLocalEvent = useEventStore((store) => store.addLocalEvent);
  const planEntries = useProvisionStore((store) => store.planEntries);
  const togglePlan = useProvisionStore((store) => store.togglePlan);
  const provisionEvents = useProvisionStore((store) => store.events);
  const applyProvisionEvent = useProvisionStore((store) => store.applyEvent);
  const applyApprovalEvent = useApprovalStore((store) => store.applyEvent);
  const applyKanbanEvent = useKanbanStore((store) => store.applyEvent);
  const pendingApprovals = useApprovalStore((store) => store.entries.filter((entry) => entry.status === "pending").length);
  const muted = useVoiceMuteStore((store) => store.muted);
  const refreshDashboard = useDashboardStore((store) => store.refresh);

  React.useEffect(() => {
    void refreshDashboard(apiBaseUrl);
    const id = window.setInterval(() => void refreshDashboard(apiBaseUrl), DASHBOARD_REFRESH_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [refreshDashboard]);

  const [activeNav, setActiveNav] = React.useState<NavKey>("overview");
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(false);
  const [search, setSearch] = React.useState("");
  const [onboardingRecord, setOnboardingRecord] = React.useState<OnboardingRecord | null>(null);
  const [draft, setDraft] = React.useState("");
  const [chatBusy, setChatBusy] = React.useState(false);

  const { audit, refreshAudit, job, jobEvents, selectedJobId, selectJob, refreshJob } = useAuditAndJobInspector(lastEvent);

  React.useEffect(() => {
    if (!lastEvent) return;
    applyProvisionEvent(lastEvent);
    applyApprovalEvent(lastEvent);
    applyKanbanEvent(lastEvent);
  }, [applyApprovalEvent, applyKanbanEvent, applyProvisionEvent, lastEvent]);

  const latestPlattEntry = [...messages].reverse().find((message) => message.author === "platt") ?? null;
  const latestPlattMessage = latestPlattEntry?.text ?? "";
  useSpeechSynthesis({ state, muted, text: latestPlattMessage, messageId: latestPlattEntry?.id ?? null });

  const provisionLabel = provisionStatusLabel(deriveProvisionSteps(provisionEvents));

  const sendMessage = React.useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || chatBusy) return;

      setChatBusy(true);
      addOperatorMessage(text);
      setDraft("");

      try {
        const path = onboardingRecord ? `/onboarding/${encodeURIComponent(onboardingRecord.id)}/chat` : "/chat";
        const response = await postJson<{ job_id: string }>(path, { prompt: text });
        selectJob(response.job_id);
      } catch {
        addLocalEvent("concerned", "Backend chat request failed");
      } finally {
        setChatBusy(false);
      }
    },
    [addLocalEvent, addOperatorMessage, chatBusy, onboardingRecord, selectJob],
  );

  const onChatSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void sendMessage(draft);
  };

  const runStateCycle = React.useCallback(async () => {
    try {
      await postJson("/dev/state-cycle");
    } catch {
      addLocalEvent("concerned", "Backend state cycle request failed");
    }
  }, [addLocalEvent]);

  return (
    <div className="dashboardShell">
      <Sidebar active={activeNav} onSelect={setActiveNav} collapsed={sidebarCollapsed} onToggleCollapsed={() => setSidebarCollapsed((c) => !c)} pendingApprovals={pendingApprovals} />
      <div className="dashboardMain">
        <TopBar title={navTitles[activeNav]} plattState={state} alertCount={alertEntryCount(audit.data)} search={search} onSearchChange={setSearch} />
        <div className="stagePillRow">
          <span className={`readinessBadge ${readiness}`} aria-live="polite">backend {readiness}</span>
          <span className={`connectionBadge ${connection}`}>{connection}</span>
          {provisionLabel ? <span className="provisionLabel">· {provisionLabel}</span> : null}
          <span className="sandboxBadge" aria-label="Sandbox environment">Sandbox</span>
        </div>
        <main className="dashboardContent" aria-label={navTitles[activeNav]}>
          {activeNav === "overview" ? (
            <OverviewView apiBaseUrl={apiBaseUrl} lastEvent={lastEvent} audit={audit.data} onSelectJob={selectJob} events={events} connection={connection} />
          ) : activeNav === "jobs" ? (
            <JobsView
              messages={messages}
              planEntries={planEntries}
              onTogglePlan={togglePlan}
              draft={draft}
              onDraftChange={setDraft}
              busy={chatBusy}
              onSubmit={onChatSubmit}
              onAutoSend={sendMessage}
              onStateCycle={() => void runStateCycle()}
              selectedJobId={selectedJobId}
              job={job}
              jobEvents={jobEvents}
              onRefreshJob={refreshJob}
            />
          ) : activeNav === "provisioning" ? (
            <ProvisioningView lastEvent={lastEvent} onboardingRecord={onboardingRecord} onOnboardingRecordChange={setOnboardingRecord} onPlanJobAccepted={selectJob} postJson={postJson} />
          ) : activeNav === "pipelines" ? (
            <PipelinesView />
          ) : activeNav === "moduleGraph" ? (
            <div className="moduleGraphViewGrid"><ModuleGraphCard tall /></div>
          ) : activeNav === "boards" ? (
            <div className="boardsViewGrid"><BoardsBoard lastEvent={lastEvent} /></div>
          ) : activeNav === "audit" ? (
            <AuditView audit={audit} onRefreshAudit={refreshAudit} selectedJobId={selectedJobId} onSelectJob={selectJob} job={job} jobEvents={jobEvents} onRefreshJob={refreshJob} />
          ) : activeNav === "approvals" ? (
            <ApprovalsView apiBaseUrl={apiBaseUrl} lastEvent={lastEvent} />
          ) : (
            <SettingsView apiBaseUrl={apiBaseUrl} readiness={readiness} />
          )}
        </main>
      </div>
      <div className="plattDeskDock" aria-label="Platt desk widget">
        <DeskWidgetBoundary>
          <React.Suspense fallback={null}>
            <PlattDeskWidget state={state} speech={latestPlattMessage} />
          </React.Suspense>
        </DeskWidgetBoundary>
      </div>
    </div>
  );
}

function ConnectedApp() {
  const lastEvent = useBackendEvents();
  const readiness = useBackendReadiness();

  return <DashboardShell readiness={readiness} lastEvent={lastEvent} />;
}

function BackendConfigurationRequired({ configuration }: { configuration: BackendConfiguration }) {
  return (
    <main className="configurationGuard">
      <section className="configurationCard" aria-labelledby="backend-configuration-title">
        <CircleAlert size={28} aria-hidden="true" />
        <p className="eyebrow">Backend configuration required</p>
        <h1 id="backend-configuration-title">Platt is not connected to a hosted API.</h1>
        <p>{configuration.message}</p>
        <p>Set those build-time variables to an approved backend, then redeploy this frontend.</p>
      </section>
    </main>
  );
}

function App() {
  return backendConfiguration.isConfigured ? <ConnectedApp /> : <BackendConfigurationRequired configuration={backendConfiguration} />;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
