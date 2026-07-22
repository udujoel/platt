import { describe, expect, it } from "vitest";

import { applyPlanReady, applyProvisionEvent, deriveProvisionSteps, provisionStatusLabel, togglePlanCollapsed } from "./provision-store";
import type { PlanEntry, ProvisionState, ProvisionStep } from "./provision-store";
import type { BackendEvent } from "../backend-events";

function event(partial: Partial<BackendEvent> & { type: BackendEvent["type"] }, at: string): BackendEvent {
  return { id: `${partial.type}-${at}`, created_at: at, ...partial } as BackendEvent;
}

describe("deriveProvisionSteps", () => {
  it("starts every step pending with no events", () => {
    expect(deriveProvisionSteps([])).toEqual([
      { id: "extracting", label: "Extracting requirements", status: "pending" },
      { id: "work_items", label: "Creating work items", status: "pending" },
      { id: "pr", label: "Opening pull request", status: "pending" },
      { id: "plan", label: "Building plan", status: "pending" },
      { id: "approval", label: "Awaiting approval", status: "pending" },
      { id: "apply", label: "Applying", status: "pending" },
      { id: "done", label: "Done", status: "pending" },
    ]);
  });

  it("marks extracting active on job_created", () => {
    const steps = deriveProvisionSteps([event({ type: "job_created", job_id: "job-1", prompt: "x" }, "t1")]);
    expect(step(steps, "extracting").status).toBe("active");
    expect(step(steps, "work_items").status).toBe("pending");
  });

  it("walks the full happy path through to done", () => {
    const events: BackendEvent[] = [
      event({ type: "job_created", job_id: "job-1", prompt: "x" }, "t1"),
      event({ type: "work_item_moved", job_id: "job-1", work_item_id: "wi-1", title: "t", from_state: "New", to_state: "Doing" }, "t2"),
      event({ type: "pipeline_update", job_id: "job-1", pipeline_name: "ci", status: "running" }, "t3"),
      event({ type: "plan_ready", job_id: "job-1", summary: "do the thing", has_blocking_changes: false }, "t4"),
      event({ type: "approval_required", job_id: "job-1", approval_id: "ap-1", summary: "confirm" }, "t5"),
      event({ type: "approval_result", job_id: "job-1", approval_id: "ap-1", approved: true }, "t6"),
      event({ type: "apply_result", job_id: "job-1", success: true, summary: "applied" }, "t7"),
    ];

    const steps = deriveProvisionSteps(events);
    expect(steps.map((s) => s.status)).toEqual(["complete", "complete", "complete", "complete", "complete", "complete", "complete"]);
  });

  it("marks the approval step itself as errored when rejected, leaving apply untouched", () => {
    const rejected = deriveProvisionSteps([
      event({ type: "approval_required", job_id: "job-1", approval_id: "ap-1", summary: "confirm" }, "t1"),
      event({ type: "approval_result", job_id: "job-1", approval_id: "ap-1", approved: false }, "t2"),
    ]);
    expect(step(rejected, "approval").status).toBe("error");
    expect(step(rejected, "apply").status).toBe("pending");
  });

  it("marks apply and done as errored when apply itself fails", () => {
    const applyFailed = deriveProvisionSteps([
      event({ type: "apply_result", job_id: "job-1", success: false, summary: "boom" }, "t1"),
    ]);
    expect(step(applyFailed, "apply").status).toBe("error");
    expect(step(applyFailed, "done").status).toBe("error");
  });

  it("ignores events for a different job when a jobId filter is supplied", () => {
    const events: BackendEvent[] = [
      event({ type: "job_created", job_id: "job-1", prompt: "x" }, "t1"),
      event({ type: "apply_result", job_id: "job-2", success: true, summary: "applied" }, "t2"),
    ];
    const steps = deriveProvisionSteps(events, "job-1");
    expect(step(steps, "extracting").status).toBe("active");
    expect(step(steps, "done").status).toBe("pending");
  });
});

describe("provisionStatusLabel", () => {
  it("returns null when nothing has started", () => {
    expect(provisionStatusLabel(deriveProvisionSteps([]))).toBeNull();
  });

  it("maps a plan that's ready for review to 'Plan ready for review', not 'running'", () => {
    const steps = deriveProvisionSteps([
      event({ type: "plan_ready", job_id: "job-1", summary: "s", has_blocking_changes: false }, "t1"),
    ]);
    expect(provisionStatusLabel(steps)).toBe("Plan ready for review");
  });

  it("maps the awaiting-approval step to 'Waiting for your approval'", () => {
    const steps = deriveProvisionSteps([
      event({ type: "approval_required", job_id: "job-1", approval_id: "ap-1", summary: "s" }, "t1"),
    ]);
    expect(provisionStatusLabel(steps)).toBe("Waiting for your approval");
  });

  it("maps an active apply step to 'Applying'", () => {
    const steps = deriveProvisionSteps([
      event({ type: "approval_required", job_id: "job-1", approval_id: "ap-1", summary: "s" }, "t1"),
      event({ type: "approval_result", job_id: "job-1", approval_id: "ap-1", approved: true }, "t2"),
    ]);
    expect(provisionStatusLabel(steps)).toBe("Applying");
  });

  it("reports completion once done is complete", () => {
    const steps = deriveProvisionSteps([event({ type: "apply_result", job_id: "job-1", success: true, summary: "s" }, "t1")]);
    expect(provisionStatusLabel(steps)).toBe("Provision complete");
  });

  it("surfaces an error state ahead of any other mapping", () => {
    const steps = deriveProvisionSteps([event({ type: "apply_result", job_id: "job-1", success: false, summary: "s" }, "t1")]);
    expect(provisionStatusLabel(steps)).toBe("Provision needs attention");
  });

  it("also surfaces an error state when the approval itself was rejected", () => {
    const steps = deriveProvisionSteps([
      event({ type: "approval_required", job_id: "job-1", approval_id: "ap-1", summary: "confirm" }, "t1"),
      event({ type: "approval_result", job_id: "job-1", approval_id: "ap-1", approved: false }, "t2"),
    ]);
    expect(provisionStatusLabel(steps)).toBe("Provision needs attention");
  });
});

describe("applyProvisionEvent", () => {
  const empty: ProvisionState = { activeJobId: null, events: [], planEntries: [] };

  it("adopts the first job it sees without requiring a job_created event", () => {
    const state = applyProvisionEvent(empty, event({ type: "approval_required", job_id: "job-1", approval_id: "ap-1", summary: "s" }, "t1"));
    expect(state.activeJobId).toBe("job-1");
    expect(state.events).toHaveLength(1);
  });

  it("accumulates events and plan entries for the active job", () => {
    let state = applyProvisionEvent(empty, event({ type: "job_created", job_id: "job-1", prompt: "x" }, "t1"));
    state = applyProvisionEvent(state, event({ type: "plan_ready", job_id: "job-1", summary: "do the thing", has_blocking_changes: false }, "t2"));
    expect(state.events).toHaveLength(2);
    expect(state.planEntries).toHaveLength(1);
    expect(state.planEntries[0].jobId).toBe("job-1");
  });

  it("resets events and plan entries when a new job's job_created event arrives", () => {
    let state = applyProvisionEvent(empty, event({ type: "job_created", job_id: "job-1", prompt: "x" }, "t1"));
    state = applyProvisionEvent(state, event({ type: "plan_ready", job_id: "job-1", summary: "old plan", has_blocking_changes: false }, "t2"));
    expect(state.planEntries).toHaveLength(1);

    state = applyProvisionEvent(state, event({ type: "job_created", job_id: "job-2", prompt: "y" }, "t3"));

    expect(state.activeJobId).toBe("job-2");
    expect(state.events).toHaveLength(1);
    expect(state.events[0].type).toBe("job_created");
    expect(state.planEntries).toHaveLength(0);
  });

  it("drops stale events for a job that is no longer active", () => {
    let state = applyProvisionEvent(empty, event({ type: "job_created", job_id: "job-1", prompt: "x" }, "t1"));
    state = applyProvisionEvent(state, event({ type: "job_created", job_id: "job-2", prompt: "y" }, "t2"));

    const beforeStaleEvent = state;
    state = applyProvisionEvent(state, event({ type: "plan_ready", job_id: "job-1", summary: "stale plan", has_blocking_changes: false }, "t3"));

    expect(state).toEqual(beforeStaleEvent);
    expect(state.planEntries).toHaveLength(0);
  });
});

describe("plan block collapse/expand", () => {
  const planReadyEvent = { id: "plan-1", job_id: "job-1", summary: "Provision a storage account", created_at: "t1" };

  it("adds a new plan entry expanded by default", () => {
    const entries = applyPlanReady([], planReadyEvent);
    expect(entries).toEqual<PlanEntry[]>([
      { id: "plan-1", jobId: "job-1", summary: "Provision a storage account", createdAt: "t1", collapsed: false },
    ]);
  });

  it("does not duplicate an entry already seen", () => {
    const first = applyPlanReady([], planReadyEvent);
    const second = applyPlanReady(first, planReadyEvent);
    expect(second).toHaveLength(1);
  });

  it("toggles collapsed state for the matching entry only", () => {
    const entries: PlanEntry[] = [
      { id: "plan-1", jobId: "job-1", summary: "a", createdAt: "t1", collapsed: false },
      { id: "plan-2", jobId: "job-1", summary: "b", createdAt: "t2", collapsed: false },
    ];

    const collapsed = togglePlanCollapsed(entries, "plan-1");
    expect(collapsed.find((e) => e.id === "plan-1")?.collapsed).toBe(true);
    expect(collapsed.find((e) => e.id === "plan-2")?.collapsed).toBe(false);

    const expanded = togglePlanCollapsed(collapsed, "plan-1");
    expect(expanded.find((e) => e.id === "plan-1")?.collapsed).toBe(false);
  });
});

function step(steps: ProvisionStep[], id: ProvisionStep["id"]): ProvisionStep {
  const found = steps.find((s) => s.id === id);
  if (!found) throw new Error(`missing step ${id}`);
  return found;
}
