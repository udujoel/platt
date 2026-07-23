import React from "react";
import { Radio } from "lucide-react";
import type { PlattState } from "../backend-events";

export type FeedEvent = { id: string; label: string; timestamp: string; state: PlattState };

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

export function EventFeedCard({ events, connection }: { events: FeedEvent[]; connection: "connecting" | "connected" | "disconnected" }) {
  return (
    <section className="dashCard eventFeedCard" aria-labelledby="event-feed-heading">
      <header className="dashCardHeader">
        <h2 id="event-feed-heading"><Radio size={14} aria-hidden="true" /> Live event feed</h2>
        <span className={`connectionDot ${connection}`} aria-label={`Stream ${connection}`} />
      </header>
      <ol className="eventFeedList">
        {events.map((event) => (
          <li key={event.id}>
            <span className="eventFeedTime">{event.timestamp}</span>
            <strong>{stateLabels[event.state]}</strong>
            <p>{event.label}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
