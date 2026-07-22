import { create } from "zustand";
import type { BackendEvent } from "../backend-events";

export const provisionStepOrder = ["extracting", "work_items", "pr", "plan", "approval", "apply", "done"] as const;

export type ProvisionStepId = (typeof provisionStepOrder)[number];
export type ProvisionStepStatus = "pending" | "active" | "complete" | "error";

export type ProvisionStep = {
  id: ProvisionStepId;
  label: string;
  status: ProvisionStepStatus;
};

const stepLabels: Record<ProvisionStepId, string> = {
  extracting: "Extracting requirements",
  work_items: "Creating work items",
  pr: "Opening pull request",
  plan: "Building plan",
  approval: "Awaiting approval",
  apply: "Applying",
  done: "Done",
};

const relevantEventTypes = new Set<BackendEvent["type"]>([
  "job_created",
  "work_item_moved",
  "pipeline_update",
  "plan_ready",
  "approval_required",
  "approval_result",
  "apply_result",
]);

/**
 * Derives the provision timeline purely from the ordered event sequence — no
 * event carries an explicit "step" field, so this is the single source of
 * truth for where a job sits in extracting -> work items -> PR -> plan ->
 * awaiting approval -> apply -> done.
 */
export function deriveProvisionSteps(events: BackendEvent[], jobId?: string): ProvisionStep[] {
  const statuses = new Map<ProvisionStepId, ProvisionStepStatus>(provisionStepOrder.map((id) => [id, "pending"]));

  const setActive = (index: number) => {
    for (let i = 0; i < index; i += 1) {
      const id = provisionStepOrder[i];
      const current = statuses.get(id);
      if (current !== "complete" && current !== "error") statuses.set(id, "complete");
    }
    if (statuses.get(provisionStepOrder[index]) !== "complete") statuses.set(provisionStepOrder[index], "active");
  };

  const sorted = [...events]
    .filter((event) => relevantEventTypes.has(event.type))
    .filter((event) => !jobId || !("job_id" in event) || event.job_id === jobId)
    .sort((a, b) => a.created_at.localeCompare(b.created_at));

  for (const event of sorted) {
    switch (event.type) {
      case "job_created":
        setActive(0);
        break;
      case "work_item_moved":
        setActive(1);
        break;
      case "pipeline_update":
        setActive(2);
        break;
      case "plan_ready":
        setActive(3);
        break;
      case "approval_required":
        setActive(4);
        break;
      case "approval_result":
        // A rejection stops the run at the approval gate — apply never starts,
        // so the failure belongs on the approval step, not on apply.
        statuses.set("approval", event.approved ? "complete" : "error");
        if (event.approved) statuses.set("apply", "active");
        break;
      case "apply_result":
        statuses.set("apply", event.success ? "complete" : "error");
        statuses.set("done", event.success ? "complete" : "error");
        break;
      default:
        break;
    }
  }

  return provisionStepOrder.map((id) => ({ id, label: stepLabels[id], status: statuses.get(id) ?? "pending" }));
}

const activeStepLabels: Record<ProvisionStepId, string> = {
  extracting: "Extracting requirements",
  work_items: "Creating work items",
  pr: "Opening pull request",
  plan: "Plan ready for review",
  approval: "Waiting for your approval",
  apply: "Applying",
  done: "Done",
};

/** Maps the derived timeline to the words shown in the bottom-left status chip. */
export function provisionStatusLabel(steps: ProvisionStep[]): string | null {
  const errored = steps.find((step) => step.status === "error");
  if (errored) return "Provision needs attention";

  const active = steps.find((step) => step.status === "active");
  if (active) return activeStepLabels[active.id];

  const done = steps.find((step) => step.id === "done");
  if (done?.status === "complete") return "Provision complete";

  return null;
}

export type PlanEntry = {
  id: string;
  jobId: string;
  summary: string;
  createdAt: string;
  collapsed: boolean;
};

type PlanReadyLike = { id: string; job_id: string; summary: string; created_at: string };

export function applyPlanReady(entries: PlanEntry[], event: PlanReadyLike): PlanEntry[] {
  if (entries.some((entry) => entry.id === event.id)) return entries;
  return [...entries, { id: event.id, jobId: event.job_id, summary: event.summary, createdAt: event.created_at, collapsed: false }];
}

export function togglePlanCollapsed(entries: PlanEntry[], id: string): PlanEntry[] {
  return entries.map((entry) => (entry.id === id ? { ...entry, collapsed: !entry.collapsed } : entry));
}

export type ProvisionState = {
  activeJobId: string | null;
  events: BackendEvent[];
  planEntries: PlanEntry[];
};

const emptyProvisionState: ProvisionState = { activeJobId: null, events: [], planEntries: [] };

/**
 * Scopes the provision timeline + plan blocks to a single active job. A new
 * job_created for a different job resets the state so a fresh run doesn't
 * inherit the previous job's steps or plan; events for a job other than the
 * currently tracked one are treated as stale and dropped.
 */
export function applyProvisionEvent(state: ProvisionState, event: BackendEvent): ProvisionState {
  if (!relevantEventTypes.has(event.type)) return state;
  const eventJobId = "job_id" in event ? event.job_id : undefined;
  if (!eventJobId) return state;

  if (event.type === "job_created" && state.activeJobId && eventJobId !== state.activeJobId) {
    return { activeJobId: eventJobId, events: [event], planEntries: [] };
  }

  if (state.activeJobId && eventJobId !== state.activeJobId) return state;

  const events = [...state.events, event].slice(-500);
  const planEntries = event.type === "plan_ready" ? applyPlanReady(state.planEntries, event) : state.planEntries;
  return { activeJobId: state.activeJobId ?? eventJobId, events, planEntries };
}

type ProvisionStore = ProvisionState & {
  seenEventIds: string[];
  applyEvent: (event: BackendEvent) => void;
  togglePlan: (id: string) => void;
};

export const useProvisionStore = create<ProvisionStore>((set) => ({
  ...emptyProvisionState,
  seenEventIds: [],
  applyEvent: (event) =>
    set((current) => {
      if (current.seenEventIds.includes(event.id)) return current;
      const seenEventIds = [...current.seenEventIds, event.id].slice(-500);
      const next = applyProvisionEvent(current, event);
      return { ...next, seenEventIds };
    }),
  togglePlan: (id) => set((current) => ({ planEntries: togglePlanCollapsed(current.planEntries, id) })),
}));
