import { describe, expect, it, vi } from "vitest";

import { applyApprovalRequired, applyApprovalResult, postApprovalDecision } from "./approval-store";

describe("applyApprovalRequired", () => {
  it("adds a pending entry for a newly requested approval", () => {
    const entries = applyApprovalRequired([], { approval_id: "appr-1", job_id: "job-1", summary: "Apply storage account" });
    expect(entries).toEqual([
      { id: "appr-1", jobId: "job-1", summary: "Apply storage account", status: "pending", deciding: false, error: null },
    ]);
  });

  it("does not duplicate an approval already tracked", () => {
    const first = applyApprovalRequired([], { approval_id: "appr-1", job_id: "job-1", summary: "Apply storage account" });
    const second = applyApprovalRequired(first, { approval_id: "appr-1", job_id: "job-1", summary: "Apply storage account" });
    expect(second).toHaveLength(1);
  });
});

describe("applyApprovalResult", () => {
  it("reflects an approved decision onto the matching entry", () => {
    const entries = applyApprovalRequired([], { approval_id: "appr-1", job_id: "job-1", summary: "Apply storage account" });
    const next = applyApprovalResult(entries, { approval_id: "appr-1", approved: true });
    expect(next[0].status).toBe("approved");
  });

  it("reflects a rejected decision onto the matching entry", () => {
    const entries = applyApprovalRequired([], { approval_id: "appr-1", job_id: "job-1", summary: "Apply storage account" });
    const next = applyApprovalResult(entries, { approval_id: "appr-1", approved: false });
    expect(next[0].status).toBe("rejected");
  });

  it("leaves unrelated entries untouched", () => {
    const entries = applyApprovalRequired([], { approval_id: "appr-1", job_id: "job-1", summary: "Apply storage account" });
    const next = applyApprovalResult(entries, { approval_id: "appr-other", approved: true });
    expect(next[0].status).toBe("pending");
  });
});

describe("postApprovalDecision", () => {
  it("POSTs the decision to /approvals/{id}/decide with an explicit operator approver, never auto-approving", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: "approved" }) });

    const result = await postApprovalDecision("http://api.test", "appr-1", "approved", fetchImpl as unknown as typeof fetch);

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://api.test/approvals/appr-1/decide",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ approver: "operator", decision: "approved" }),
      }),
    );
    expect(result).toEqual({ status: "approved" });
  });

  it("throws with the server's detail message when the decision request fails", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({ ok: false, status: 409, json: async () => ({ detail: "approval already decided" }) });

    await expect(postApprovalDecision("http://api.test", "appr-1", "rejected", fetchImpl as unknown as typeof fetch)).rejects.toThrow(
      "approval already decided",
    );
  });
});
