import { ReconnectPolicy } from "./reconnect-policy";
import { parseBackendEvent } from "./backend-events";
import type { BackendEvent } from "./backend-events";

export type SseFrame = {
  id: string | null;
  event: string | null;
  data: string;
};

export type SseConnectionState = "connecting" | "connected" | "disconnected";

/**
 * Incrementally parses a text/event-stream body into frames. Frames may span
 * multiple chunks (or several frames may land in one chunk), so partial
 * trailing lines are buffered until the next push.
 */
export function createSseFrameParser() {
  let buffer = "";
  let dataLines: string[] = [];
  let eventType: string | null = null;
  let eventId: string | null = null;

  function dispatch(): SseFrame | null {
    const frame = dataLines.length > 0 ? { id: eventId, event: eventType, data: dataLines.join("\n") } : null;
    dataLines = [];
    eventType = null;
    return frame;
  }

  function processLine(line: string): SseFrame | null {
    if (line === "") return dispatch();
    if (line.startsWith(":")) return null; // keep-alive comment

    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    let value = separator === -1 ? "" : line.slice(separator + 1);
    if (value.startsWith(" ")) value = value.slice(1);

    if (field === "data") dataLines.push(value);
    else if (field === "event") eventType = value;
    else if (field === "id") eventId = value;
    return null;
  }

  return {
    push(chunk: string): SseFrame[] {
      buffer += chunk;
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      const frames: SseFrame[] = [];
      for (const rawLine of lines) {
        const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
        const frame = processLine(line);
        if (frame) frames.push(frame);
      }
      return frames;
    },
  };
}

export function parseSseFrameEvent(frame: SseFrame): BackendEvent | null {
  try {
    return parseBackendEvent(JSON.parse(frame.data) as unknown);
  } catch {
    return null;
  }
}

/**
 * Tracks the highest `seq` seen (the frame's `id`, per the SSE contract) so a
 * reconnect can resend it as `Last-Event-ID` and so replayed frames that
 * arrive again around a reconnect boundary are dropped rather than
 * re-delivered.
 */
export function createSseResumeTracker(initialLastEventId: string | null = null) {
  let lastSeq = parseSeq(initialLastEventId);

  function parseSeq(value: string | null): number | null {
    if (value === null) return null;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }

  return {
    get lastEventId(): string | null {
      return lastSeq === null ? null : String(lastSeq);
    },
    /** Returns false when this frame is a duplicate that should be skipped. */
    shouldProcess(frame: SseFrame): boolean {
      const seq = parseSeq(frame.id);
      if (seq === null) return true;
      if (lastSeq !== null && seq <= lastSeq) return false;
      lastSeq = seq;
      return true;
    },
  };
}

export type SseClientOptions = {
  streamUrl: () => string;
  onEvent: (event: BackendEvent) => void;
  onConnectionChange: (state: SseConnectionState) => void;
  onUnparsableFrame?: () => void;
  fetchImpl?: typeof fetch;
  reconnectPolicy?: ReconnectPolicy;
};

/**
 * Resumable SSE client built on `fetch` (rather than `EventSource`) so we can
 * set the `Last-Event-ID` header ourselves on every reconnect attempt,
 * including the ones after the server's ~25s idle close where a plain
 * `EventSource` would otherwise start over from the top.
 */
export function createSseClient(options: SseClientOptions) {
  const fetchImpl = options.fetchImpl ?? fetch;
  const reconnectPolicy = options.reconnectPolicy ?? new ReconnectPolicy();
  const resumeTracker = createSseResumeTracker();
  let closed = false;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let abortController: AbortController | undefined;

  function scheduleReconnect(delayMs: number) {
    if (closed) return;
    globalThis.clearTimeout(retryTimer);
    retryTimer = globalThis.setTimeout(() => {
      retryTimer = undefined;
      void connect();
    }, delayMs);
  }

  async function connect() {
    if (closed) return;
    options.onConnectionChange("connecting");
    abortController = new AbortController();

    try {
      const lastEventId = resumeTracker.lastEventId;
      const response = await fetchImpl(options.streamUrl(), {
        signal: abortController.signal,
        headers: lastEventId ? { "Last-Event-ID": lastEventId } : undefined,
      });

      if (!response.ok || !response.body) {
        throw new Error(`SSE request failed: ${response.status}`);
      }

      options.onConnectionChange("connected");
      const parser = createSseFrameParser();
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const frames = parser.push(decoder.decode(value, { stream: true }));
        for (const frame of frames) {
          reconnectPolicy.reset();
          if (!resumeTracker.shouldProcess(frame)) continue;

          const event = parseSseFrameEvent(frame);
          if (event) options.onEvent(event);
          else options.onUnparsableFrame?.();
        }
      }

      if (closed) return;
      // A clean end-of-stream is the server's ~25s cap, not a failure — reconnect
      // immediately (with Last-Event-ID) instead of backing off.
      options.onConnectionChange("disconnected");
      reconnectPolicy.reset();
      scheduleReconnect(0);
    } catch (error) {
      if (closed || (error instanceof DOMException && error.name === "AbortError")) return;
      options.onConnectionChange("disconnected");
      scheduleReconnect(reconnectPolicy.nextDelayMs());
    }
  }

  return {
    start() {
      void connect();
    },
    close() {
      closed = true;
      globalThis.clearTimeout(retryTimer);
      abortController?.abort();
    },
  };
}
