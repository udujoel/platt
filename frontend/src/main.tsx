import React from "react";
import ReactDOM from "react-dom/client";
import { SendHorizonal } from "lucide-react";
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
};

type EventStore = {
  state: PlattState;
  events: EventEntry[];
  messages: ChatMessage[];
  setState: (state: PlattState, label: string) => void;
  sendMessage: (text: string) => void;
};

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

const fakeCycle: Array<{ state: PlattState; label: string }> = [
  { state: "listening", label: "Chat input focused" },
  { state: "thinking", label: "Planning response" },
  { state: "working", label: "Tool execution in flight" },
  { state: "talking", label: "Streaming response" },
  { state: "awaiting_approval", label: "Plan approval required" },
  { state: "celebrating", label: "Apply succeeded" },
  { state: "concerned", label: "Pipeline error detected" },
  { state: "idle", label: "Returned to idle" },
];

const createId = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;

const useEventStore = create<EventStore>((set) => ({
  state: "idle",
  events: [
    {
      id: createId(),
      label: "Phase 1 shell mounted",
      timestamp: new Date().toLocaleTimeString(),
      state: "idle",
    },
  ],
  messages: [
    {
      id: createId(),
      author: "platt",
      text: "Phase 1 interface ready. Live agent integration is not connected yet.",
    },
  ],
  setState: (state, label) =>
    set((current) => ({
      state,
      events: [
        { id: createId(), label, timestamp: new Date().toLocaleTimeString(), state },
        ...current.events,
      ].slice(0, 8),
    })),
  sendMessage: (text) =>
    set((current) => ({
      state: "thinking",
      messages: [
        ...current.messages,
        { id: createId(), author: "operator", text },
        { id: createId(), author: "platt", text: "Acknowledged in fake cycle mode." },
      ],
      events: [
        {
          id: createId(),
          label: "Operator message captured",
          timestamp: new Date().toLocaleTimeString(),
          state: "thinking" as PlattState,
        },
        ...current.events,
      ].slice(0, 8),
    })),
}));

function useFakeStateCycle() {
  React.useEffect(() => {
    let index = 0;
    const interval = window.setInterval(() => {
      const next = fakeCycle[index % fakeCycle.length];
      useEventStore.getState().setState(next.state, next.label);
      index += 1;
    }, 2600);

    return () => window.clearInterval(interval);
  }, []);
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

  return (
    <section className="stage" aria-label="Platt avatar stage">
      <div className="stageHeader">
        <StatusChip state={state} />
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
        <span>R3F scene</span>
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
  const sendMessage = useEventStore((store) => store.sendMessage);
  const [draft, setDraft] = React.useState("");

  const onSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    sendMessage(text);
    setDraft("");
  };

  return (
    <aside className="chatPanel" aria-label="Chat and event timeline">
      <div className="panelSection messages">
        <header>
          <h1>Platt</h1>
          <p>Phase 1 shell</p>
        </header>
        <div className="messageList">
          {messages.map((message) => (
            <div className={`message ${message.author}`} key={message.id}>
              <span>{message.author === "platt" ? "Platt" : "Operator"}</span>
              <p>{message.text}</p>
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
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Send a fake-cycle message"
          />
          <button type="submit" aria-label="Send message" title="Send message">
            <SendHorizonal size={18} aria-hidden="true" />
          </button>
        </div>
      </form>
    </aside>
  );
}

function App() {
  useFakeStateCycle();
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
