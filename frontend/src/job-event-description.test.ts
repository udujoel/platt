import { describe, expect, it } from "vitest";

import { describePersistedEvent } from "./job-event-description";

describe("describePersistedEvent", () => {
  it("retains the planned step identity in an execution receipt", () => {
    expect(
      describePersistedEvent({
        id: "event-1",
        job_id: "job-1",
        type: "audit_entry",
        created_at: "2026-07-18T02:45:00Z",
        payload: JSON.stringify({
          tool: "repo.read_file",
          action: "execute_plan_step",
          outcome: "succeeded",
          step_id: "provider-constraints",
          summary: "Read versions.tf; returned 166 bytes.",
        }),
      }),
    ).toEqual({
      title: "repo.read_file · execute_plan_step · provider-constraints",
      detail: "succeeded — Read versions.tf; returned 166 bytes.",
    });
  });
});
