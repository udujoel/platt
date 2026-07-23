import React from "react";
import { ShieldCheck } from "lucide-react";
import { ApprovalGate } from "./ApprovalCard";
import { useApprovalStore } from "./approval-store";
import type { BackendEvent } from "../backend-events";

export function ApprovalsView({ apiBaseUrl, lastEvent }: { apiBaseUrl: string; lastEvent: BackendEvent | null }) {
  const entries = useApprovalStore((store) => store.entries);

  return (
    <div className="approvalsViewGrid">
      {entries.length === 0 ? (
        <div className="dashCard emptyStateCard">
          <div className="emptyState">
            <ShieldCheck size={20} aria-hidden="true" />
            <strong>No approval gates pending</strong>
            <p>Approvals raised by provisioning jobs will appear here for you to approve or reject.</p>
          </div>
        </div>
      ) : (
        <ApprovalGate apiBaseUrl={apiBaseUrl} lastEvent={lastEvent} />
      )}
    </div>
  );
}
