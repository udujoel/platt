export type PlattState =
  | "idle"
  | "listening"
  | "thinking"
  | "working"
  | "talking"
  | "awaiting_approval"
  | "celebrating"
  | "concerned";

export const plattStates = new Set<PlattState>([
  "idle",
  "listening",
  "thinking",
  "working",
  "talking",
  "awaiting_approval",
  "celebrating",
  "concerned",
]);

type EventBase = {
  id: string;
  created_at: string;
};

type JobEvent = EventBase & {
  job_id?: string;
};

export type BackendEvent =
  | (JobEvent & { type: "agent_state"; job_id: string; state: PlattState; label: string })
  | (JobEvent & { type: "chat_delta"; job_id: string; delta: string; index: number; done: boolean })
  | (JobEvent & { type: "job_created"; job_id: string; prompt: string })
  | (JobEvent & { type: "work_item_moved"; job_id: string; work_item_id: string; title: string; from_state: string; to_state: string })
  | (JobEvent & { type: "pipeline_update"; job_id: string; pipeline_name: string; status: string; url?: string | null })
  | (JobEvent & { type: "plan_ready"; job_id: string; summary: string; has_blocking_changes: boolean })
  | (JobEvent & { type: "approval_required"; job_id: string; approval_id: string; summary: string })
  | (JobEvent & { type: "approval_result"; job_id: string; approval_id: string; approved: boolean })
  | (JobEvent & { type: "apply_result"; job_id: string; success: boolean; summary: string })
  | (JobEvent & { type: "audit_entry"; job_id: string; tool: string; action: string; outcome: string; step_id?: string | null; summary?: string | null })
  | (EventBase & { type: "dashboard_refresh"; metrics: Record<string, string | number> });

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function hasString(record: Record<string, unknown>, key: string): boolean {
  return typeof record[key] === "string";
}

function hasJobId(record: Record<string, unknown>): boolean {
  return hasString(record, "job_id");
}

export function parseBackendEvent(value: unknown): BackendEvent | null {
  if (!isRecord(value) || !hasString(value, "id") || !hasString(value, "created_at") || !hasString(value, "type")) return null;

  switch (value.type) {
    case "agent_state":
      return hasJobId(value) && hasString(value, "label") && typeof value.state === "string" && plattStates.has(value.state as PlattState)
        ? (value as BackendEvent)
        : null;
    case "chat_delta":
      return hasJobId(value) && hasString(value, "delta") && Number.isInteger(value.index) && (value.index as number) >= 0 && typeof value.done === "boolean"
        ? (value as BackendEvent)
        : null;
    case "job_created":
      return hasJobId(value) && hasString(value, "prompt") ? (value as BackendEvent) : null;
    case "work_item_moved":
      return hasJobId(value) && ["work_item_id", "title", "from_state", "to_state"].every((key) => hasString(value, key)) ? (value as BackendEvent) : null;
    case "pipeline_update":
      return hasJobId(value) && hasString(value, "pipeline_name") && hasString(value, "status") && (value.url === undefined || value.url === null || typeof value.url === "string")
        ? (value as BackendEvent)
        : null;
    case "plan_ready":
      return hasJobId(value) && hasString(value, "summary") && typeof value.has_blocking_changes === "boolean" ? (value as BackendEvent) : null;
    case "approval_required":
      return hasJobId(value) && hasString(value, "approval_id") && hasString(value, "summary") ? (value as BackendEvent) : null;
    case "approval_result":
      return hasJobId(value) && hasString(value, "approval_id") && typeof value.approved === "boolean" ? (value as BackendEvent) : null;
    case "apply_result":
      return hasJobId(value) && typeof value.success === "boolean" && hasString(value, "summary") ? (value as BackendEvent) : null;
    case "audit_entry":
      return hasJobId(value)
        && ["tool", "action", "outcome"].every((key) => hasString(value, key))
        && (value.step_id === undefined || value.step_id === null || typeof value.step_id === "string")
        && (value.summary === undefined || value.summary === null || typeof value.summary === "string")
        ? (value as BackendEvent)
        : null;
    case "dashboard_refresh":
      return isRecord(value.metrics) && Object.values(value.metrics).every((metric) => typeof metric === "string" || typeof metric === "number") ? (value as BackendEvent) : null;
    default:
      return null;
  }
}
