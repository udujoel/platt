import React from "react";
import { CircleAlert, ShieldCheck, ShieldX } from "lucide-react";
import { useApprovalStore } from "./approval-store";
import type { ApprovalEntry } from "./approval-store";
import type { BackendEvent } from "../backend-events";

export function ApprovalGate({ apiBaseUrl, lastEvent }: { apiBaseUrl: string; lastEvent: BackendEvent | null }) {
  const entries = useApprovalStore((store) => store.entries);
  const applyEvent = useApprovalStore((store) => store.applyEvent);
  const decide = useApprovalStore((store) => store.decide);

  React.useEffect(() => {
    if (lastEvent) applyEvent(lastEvent);
  }, [applyEvent, lastEvent]);

  if (entries.length === 0) return null;

  return (
    <div className="approvalGate" aria-label="Approval gate">
      {entries.map((entry) => (
        <ApprovalCard key={entry.id} entry={entry} onDecide={(decision) => void decide(apiBaseUrl, entry.id, decision)} />
      ))}
    </div>
  );
}

function ApprovalCard({ entry, onDecide }: { entry: ApprovalEntry; onDecide: (decision: "approved" | "rejected") => void }) {
  const resolved = entry.status !== "pending";

  return (
    <div className={`approvalCard ${entry.status}`} role="alert">
      <header>
        {entry.status === "approved" ? <ShieldCheck size={16} aria-hidden="true" /> : entry.status === "rejected" ? <ShieldX size={16} aria-hidden="true" /> : <ShieldCheck size={16} aria-hidden="true" />}
        <strong>{resolved ? `Approval ${entry.status}` : "Approval required"}</strong>
      </header>
      <p>{entry.summary}</p>
      {entry.error ? (
        <div className="approvalError">
          <CircleAlert size={14} aria-hidden="true" />
          <span>{entry.error}</span>
        </div>
      ) : null}
      {resolved ? null : (
        <div className="approvalActions">
          <button className="approveButton" type="button" onClick={() => onDecide("approved")} disabled={entry.deciding}>
            <ShieldCheck size={15} aria-hidden="true" />
            {entry.deciding ? "Submitting…" : "Approve"}
          </button>
          <button className="rejectButton" type="button" onClick={() => onDecide("rejected")} disabled={entry.deciding}>
            <ShieldX size={15} aria-hidden="true" />
            {entry.deciding ? "Submitting…" : "Reject"}
          </button>
        </div>
      )}
    </div>
  );
}
