import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createBackendReadinessPoller,
  parseBackendReadiness,
  READINESS_REQUEST_TIMEOUT_MS,
  READINESS_RETRY_INTERVAL_MS,
} from "./readiness-status";

describe("parseBackendReadiness", () => {
  it("recognizes the verified readiness contract", () => {
    expect(parseBackendReadiness({ status: "ready", persistence: "ok" })).toBe("ready");
  });

  it("treats missing or malformed readiness payloads as unavailable", () => {
    expect(parseBackendReadiness({ status: "ready" })).toBe("unavailable");
    expect(parseBackendReadiness({ status: "ok", persistence: "ok" })).toBe("unavailable");
    expect(parseBackendReadiness(null)).toBe("unavailable");
  });
});

describe("createBackendReadinessPoller", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("marks a timed-out initial request unavailable and retries it after 30 seconds", async () => {
    vi.useFakeTimers();
    const onReadiness = vi.fn();
    const requestReadiness = vi.fn(
      (signal: AbortSignal) =>
        new Promise<unknown>((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(new Error("request aborted")), { once: true });
        }),
    );
    const poller = createBackendReadinessPoller({ requestReadiness, onReadiness });

    poller.start();
    expect(requestReadiness).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(READINESS_REQUEST_TIMEOUT_MS);
    expect(onReadiness).toHaveBeenLastCalledWith("unavailable");

    await vi.advanceTimersByTimeAsync(READINESS_RETRY_INTERVAL_MS);
    expect(requestReadiness).toHaveBeenCalledTimes(2);
    poller.stop();
  });

  it("aborts an active request and prevents retries after cleanup", async () => {
    vi.useFakeTimers();
    const onAbort = vi.fn();
    const requestReadiness = vi.fn(
      (signal: AbortSignal) =>
        new Promise<unknown>((_resolve, reject) => {
          signal.addEventListener(
            "abort",
            () => {
              onAbort();
              reject(new Error("request aborted"));
            },
            { once: true },
          );
        }),
    );
    const poller = createBackendReadinessPoller({ requestReadiness, onReadiness: vi.fn() });

    poller.start();
    poller.stop();
    await vi.runAllTimersAsync();

    expect(onAbort).toHaveBeenCalledTimes(1);
    expect(requestReadiness).toHaveBeenCalledTimes(1);
  });
});
