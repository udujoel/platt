import React from "react";
import ReactDOM from "react-dom/client";
import { Play, SendHorizonal } from "lucide-react";
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

type BackendEvent =
  | {
      id: string;
      type: "agent_state";
      job_id: string;
      state: PlattState;
      label: string;
      created_at: string;
    }
  | {
      id: string;
      type: "chat_delta";
      job_id: string;
      delta: string;
      index: number;
      done: boolean;
      created_at: string;
    }
  | {
      id: string;
      type: "job_created";
      job_id: string;
      prompt: string;
      created_at: string;
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
      if (event.type === "agent_state") {
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
        const event = JSON.parse(message.data) as BackendEvent;
        useEventStore.getState().applyBackendEvent(event);
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
}

async function postJson(path: string, body?: unknown) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json();
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

function ChatPanel() {
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
      await postJson("/chat", { prompt: text });
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
  useBackendEvents();
  return (
    <main className="appShell">
      <Stage />
      <ChatPanel />
    </main>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
