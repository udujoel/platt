import { describe, expect, it, vi } from "vitest";

import { ReconnectPolicy } from "./reconnect-policy";
import {
  createSseClient,
  createSseFrameParser,
  createSseResumeTracker,
  parseSseFrameEvent,
} from "./sse-client";

const agentStateEvent = { id: "evt-1", created_at: "2026-07-21T00:00:00Z", type: "agent_state", job_id: "job-1", state: "thinking", label: "Thinking" };

function sseBody(...frames: string[]) {
  return frames.join("");
}

function streamResponse(chunks: string[]) {
  let index = 0;
  return {
    ok: true,
    body: {
      getReader() {
        return {
          async read() {
            if (index >= chunks.length) return { value: undefined, done: true };
            const chunk = chunks[index];
            index += 1;
            return { value: new TextEncoder().encode(chunk), done: false };
          },
        };
      },
    },
  } as unknown as Response;
}

describe("createSseFrameParser", () => {
  it("parses a single frame delivered in one chunk", () => {
    const parser = createSseFrameParser();
    const frames = parser.push(`id: 1\nevent: agent_state\ndata: ${JSON.stringify(agentStateEvent)}\n\n`);

    expect(frames).toHaveLength(1);
    expect(frames[0]).toMatchObject({ id: "1", event: "agent_state" });
    expect(JSON.parse(frames[0].data)).toMatchObject({ id: "evt-1" });
  });

  it("buffers a frame split across multiple chunks", () => {
    const parser = createSseFrameParser();
    const raw = `id: 2\nevent: agent_state\ndata: ${JSON.stringify(agentStateEvent)}\n\n`;
    const midpoint = Math.floor(raw.length / 2);

    expect(parser.push(raw.slice(0, midpoint))).toHaveLength(0);
    const frames = parser.push(raw.slice(midpoint));

    expect(frames).toHaveLength(1);
    expect(frames[0].id).toBe("2");
  });

  it("ignores keep-alive comment lines", () => {
    const parser = createSseFrameParser();
    const frames = parser.push(`: keep-alive\n\nid: 3\nevent: agent_state\ndata: ${JSON.stringify(agentStateEvent)}\n\n`);

    expect(frames).toHaveLength(1);
    expect(frames[0].id).toBe("3");
  });

  it("joins multi-line data fields with newlines", () => {
    const parser = createSseFrameParser();
    const frames = parser.push("event: dashboard_refresh\ndata: line one\ndata: line two\n\n");

    expect(frames[0].data).toBe("line one\nline two");
  });
});

describe("parseSseFrameEvent", () => {
  it("parses a well-formed backend event", () => {
    const event = parseSseFrameEvent({ id: "1", event: "agent_state", data: JSON.stringify(agentStateEvent) });
    expect(event).toMatchObject({ type: "agent_state", job_id: "job-1" });
  });

  it("rejects invalid JSON", () => {
    expect(parseSseFrameEvent({ id: "1", event: "agent_state", data: "{not json" })).toBeNull();
  });

  it("rejects a payload that fails schema validation", () => {
    expect(parseSseFrameEvent({ id: "1", event: "agent_state", data: JSON.stringify({ id: "x", created_at: "now", type: "agent_state" }) })).toBeNull();
  });
});

describe("createSseResumeTracker", () => {
  it("tracks the highest seq seen and exposes it as the next Last-Event-ID", () => {
    const tracker = createSseResumeTracker();

    expect(tracker.lastEventId).toBeNull();
    expect(tracker.shouldProcess({ id: "5", event: "agent_state", data: "{}" })).toBe(true);
    expect(tracker.lastEventId).toBe("5");
  });

  it("drops frames whose seq is not greater than the last seen seq", () => {
    const tracker = createSseResumeTracker("10");

    expect(tracker.shouldProcess({ id: "9", event: "agent_state", data: "{}" })).toBe(false);
    expect(tracker.shouldProcess({ id: "10", event: "agent_state", data: "{}" })).toBe(false);
    expect(tracker.shouldProcess({ id: "11", event: "agent_state", data: "{}" })).toBe(true);
    expect(tracker.lastEventId).toBe("11");
  });

  it("always processes frames without an id", () => {
    const tracker = createSseResumeTracker("10");
    expect(tracker.shouldProcess({ id: null, event: "agent_state", data: "{}" })).toBe(true);
    expect(tracker.lastEventId).toBe("10");
  });
});

describe("createSseClient", () => {
  it("delivers parsed events and resends Last-Event-ID on the following connect after a clean server close", async () => {
    const onEvent = vi.fn();
    const onConnectionChange = vi.fn();
    const firstFrame = `id: 1\nevent: agent_state\ndata: ${JSON.stringify(agentStateEvent)}\n\n`;
    const secondEvent = { ...agentStateEvent, id: "evt-2" };
    const secondFrame = `id: 2\nevent: agent_state\ndata: ${JSON.stringify(secondEvent)}\n\n`;

    let client: ReturnType<typeof createSseClient>;
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(streamResponse([sseBody(firstFrame)]))
      .mockImplementationOnce(async () => {
        // Close on the second connect (the reconnect after the clean server
        // close) so the client doesn't keep looping against the mock.
        client.close();
        return streamResponse([sseBody(secondFrame)]);
      });

    client = createSseClient({
      streamUrl: () => "https://api.example.com/events/stream",
      onEvent,
      onConnectionChange,
      fetchImpl,
      reconnectPolicy: new ReconnectPolicy(),
    });

    client.start();
    await vi.waitFor(() => expect(fetchImpl).toHaveBeenCalledTimes(2));
    await vi.waitFor(() => expect(onEvent).toHaveBeenCalledTimes(2));

    expect(fetchImpl.mock.calls[0][1]?.headers).toBeUndefined();
    expect(fetchImpl.mock.calls[1][1]?.headers).toMatchObject({ "Last-Event-ID": "1" });
  });

  it("reports connecting/connected/disconnected transitions", async () => {
    let client: ReturnType<typeof createSseClient>;
    const onConnectionChange = vi.fn((state: string) => {
      if (state === "disconnected") client.close();
    });
    const fetchImpl = vi.fn().mockResolvedValue(streamResponse([]));

    client = createSseClient({
      streamUrl: () => "https://api.example.com/events/stream",
      onEvent: vi.fn(),
      onConnectionChange,
      fetchImpl,
      reconnectPolicy: new ReconnectPolicy(),
    });

    client.start();
    await vi.waitFor(() => expect(onConnectionChange).toHaveBeenCalledWith("disconnected"));

    expect(onConnectionChange.mock.calls.map(([state]) => state)).toEqual(["connecting", "connected", "disconnected"]);
  });

  it("flags frames whose data cannot be parsed as a backend event", async () => {
    const onUnparsableFrame = vi.fn();
    const fetchImpl = vi.fn().mockResolvedValue(streamResponse(["event: agent_state\ndata: not json\n\n"]));

    const client = createSseClient({
      streamUrl: () => "https://api.example.com/events/stream",
      onEvent: vi.fn(),
      onConnectionChange: vi.fn(),
      onUnparsableFrame,
      fetchImpl,
      reconnectPolicy: new ReconnectPolicy(),
    });

    client.start();
    await vi.waitFor(() => expect(onUnparsableFrame).toHaveBeenCalledTimes(1));
    client.close();
  });
});
