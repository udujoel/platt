export type BackendReadiness = "checking" | "ready" | "unavailable";

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
