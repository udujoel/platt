export type PersistedJobEvent = {
  id: string;
  job_id: string;
  type: string;
  payload: string;
  created_at: string;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function describePersistedEvent(event: PersistedJobEvent) {
  let payload: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(event.payload);
    if (!isRecord(parsed)) throw new Error("Invalid event payload");
    payload = parsed;
  } catch {
    return { title: event.type.replace(/_/g, " "), detail: "Event payload could not be read." };
  }

  switch (event.type) {
    case "agent_state":
      return { title: String(payload.label ?? "Agent state changed"), detail: String(payload.state ?? "state") };
    case "chat_delta":
      return { title: payload.done ? "Response complete" : "Response streamed", detail: String(payload.delta ?? "") || "No visible text" };
    case "job_created":
      return { title: "Job accepted", detail: String(payload.prompt ?? "") };
    case "work_item_moved":
      return { title: String(payload.title ?? "Work item moved"), detail: `${String(payload.from_state ?? "Unknown")} → ${String(payload.to_state ?? "Unknown")}` };
    case "pipeline_update":
      return { title: String(payload.pipeline_name ?? "Pipeline updated"), detail: String(payload.status ?? "Unknown") };
    case "plan_ready":
    case "apply_result":
      return { title: event.type === "plan_ready" ? "Plan ready" : "Apply result", detail: String(payload.summary ?? "") };
    case "approval_required":
      return { title: "Approval required", detail: String(payload.summary ?? "") };
    case "approval_result":
      return { title: "Approval recorded", detail: payload.approved ? "Approved" : "Not approved" };
    case "audit_entry":
      return {
        title: `${String(payload.tool ?? "Tool")} · ${String(payload.action ?? "action")}${typeof payload.step_id === "string" ? ` · ${payload.step_id}` : ""}`,
        detail: [String(payload.outcome ?? ""), typeof payload.summary === "string" ? payload.summary : ""].filter(Boolean).join(" — "),
      };
    default:
      return { title: event.type.replace(/_/g, " "), detail: "Backend event recorded" };
  }
}
