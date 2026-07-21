import { create } from "zustand";
import type { BackendEvent } from "../backend-events";

export type ApprovalStatus = "pending" | "approved" | "rejected";

export type ApprovalEntry = {
  id: string;
  jobId: string;
  summary: string;
  status: ApprovalStatus;
  deciding: boolean;
  error: string | null;
};

type ApprovalRequiredLike = { approval_id: string; job_id: string; summary: string };
type ApprovalResultLike = { approval_id: string; approved: boolean };

export function applyApprovalRequired(entries: ApprovalEntry[], event: ApprovalRequiredLike): ApprovalEntry[] {
  if (entries.some((entry) => entry.id === event.approval_id)) return entries;
  return [
    ...entries,
    { id: event.approval_id, jobId: event.job_id, summary: event.summary, status: "pending", deciding: false, error: null },
  ];
}

export function applyApprovalResult(entries: ApprovalEntry[], event: ApprovalResultLike): ApprovalEntry[] {
  return entries.map((entry) =>
    entry.id === event.approval_id ? { ...entry, status: event.approved ? "approved" : "rejected", deciding: false } : entry,
  );
}

export type DecideApprovalResponse = { status: ApprovalStatus };

/**
 * The backend's one-time decide endpoint is the only path that can resolve
 * an approval — this never fires without an explicit operator click.
 */
export async function postApprovalDecision(
  apiBaseUrl: string,
  approvalId: string,
  decision: "approved" | "rejected",
  fetchImpl: typeof fetch = fetch,
): Promise<DecideApprovalResponse> {
  const response = await fetchImpl(`${apiBaseUrl}/approvals/${encodeURIComponent(approvalId)}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ approver: "operator", decision }),
  });

  if (!response.ok) {
    let detail = "";
    try {
      const payload: unknown = await response.json();
      if (payload && typeof payload === "object" && typeof (payload as { detail?: unknown }).detail === "string") {
        detail = (payload as { detail: string }).detail;
      }
    } catch {
      // HTTP status is the actionable fallback when the error body isn't JSON.
    }
    throw new Error(detail || `Approval decision failed: ${response.status}`);
  }

  return response.json() as Promise<DecideApprovalResponse>;
}

type ApprovalStore = {
  entries: ApprovalEntry[];
  seenEventIds: string[];
  applyEvent: (event: BackendEvent) => void;
  decide: (apiBaseUrl: string, approvalId: string, decision: "approved" | "rejected") => Promise<void>;
};

export const useApprovalStore = create<ApprovalStore>((set) => ({
  entries: [],
  seenEventIds: [],
  applyEvent: (event) =>
    set((current) => {
      if (event.type !== "approval_required" && event.type !== "approval_result") return current;
      if (current.seenEventIds.includes(event.id)) return current;
      const seenEventIds = [...current.seenEventIds, event.id].slice(-500);
      const entries = event.type === "approval_required" ? applyApprovalRequired(current.entries, event) : applyApprovalResult(current.entries, event);
      return { entries, seenEventIds };
    }),
  decide: async (apiBaseUrl, approvalId, decision) => {
    set((current) => ({
      entries: current.entries.map((entry) => (entry.id === approvalId ? { ...entry, deciding: true, error: null } : entry)),
    }));
    try {
      await postApprovalDecision(apiBaseUrl, approvalId, decision);
      set((current) => ({
        entries: current.entries.map((entry) =>
          entry.id === approvalId ? { ...entry, status: decision, deciding: false } : entry,
        ),
      }));
    } catch (reason) {
      set((current) => ({
        entries: current.entries.map((entry) =>
          entry.id === approvalId
            ? { ...entry, deciding: false, error: reason instanceof Error ? reason.message : "Could not record this decision." }
            : entry,
        ),
      }));
    }
  },
}));
