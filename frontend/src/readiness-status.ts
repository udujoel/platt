export type BackendReadiness = "checking" | "ready" | "unavailable";

export const READINESS_REQUEST_TIMEOUT_MS = 5_000;
export const READINESS_RETRY_INTERVAL_MS = 30_000;

type ReadinessRequest = (signal: AbortSignal) => Promise<unknown>;

type BackendReadinessPollerOptions = {
  requestReadiness: ReadinessRequest;
  onReadiness: (readiness: BackendReadiness) => void;
};

export function parseBackendReadiness(value: unknown): BackendReadiness {
  if (
    value !== null &&
    typeof value === "object" &&
    (value as Record<string, unknown>).status === "ready" &&
    (value as Record<string, unknown>).persistence === "ok"
  ) {
    return "ready";
  }
  return "unavailable";
}

export function createBackendReadinessPoller({
  requestReadiness,
  onReadiness,
}: BackendReadinessPollerOptions) {
  let closed = false;
  let retryTimer: number | undefined;
  let activeController: AbortController | undefined;

  const checkReadiness = async () => {
    const controller = new AbortController();
    activeController = controller;
    const timeout = globalThis.setTimeout(() => controller.abort(), READINESS_REQUEST_TIMEOUT_MS);

    try {
      const response = await requestReadiness(controller.signal);
      if (!closed) onReadiness(parseBackendReadiness(response));
    } catch {
      if (!closed) onReadiness("unavailable");
    } finally {
      globalThis.clearTimeout(timeout);
      if (activeController === controller) activeController = undefined;
      if (!closed) {
        retryTimer = globalThis.setTimeout(() => void checkReadiness(), READINESS_RETRY_INTERVAL_MS);
      }
    }
  };

  return {
    start() {
      void checkReadiness();
    },
    stop() {
      closed = true;
      activeController?.abort();
      globalThis.clearTimeout(retryTimer);
    },
  };
}
