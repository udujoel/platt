import React from "react";
import { CheckCircle2, CircleDashed, CircleDot, XCircle } from "lucide-react";
import { deriveProvisionSteps, useProvisionStore } from "./provision-store";
import { groupByColumn, kanbanColumns, useKanbanStore } from "./kanban-store";
import type { BackendEvent } from "../backend-events";

const stepIcon = { pending: CircleDashed, active: CircleDot, complete: CheckCircle2, error: XCircle } as const;

export function ProvisioningCard({ lastEvent, compact = false }: { lastEvent: BackendEvent | null; compact?: boolean }) {
  const events = useProvisionStore((store) => store.events);
  const applyProvisionEvent = useProvisionStore((store) => store.applyEvent);
  const items = useKanbanStore((store) => store.items);
  const applyKanbanEvent = useKanbanStore((store) => store.applyEvent);

  React.useEffect(() => {
    if (!lastEvent) return;
    applyProvisionEvent(lastEvent);
    applyKanbanEvent(lastEvent);
  }, [applyKanbanEvent, applyProvisionEvent, lastEvent]);

  const steps = deriveProvisionSteps(events);
  const grouped = groupByColumn(items);
  const totalItems = items.length;
  const donePercent = totalItems === 0 ? 0 : Math.round((grouped.Done.length / totalItems) * 100);

  return (
    <section className="dashCard provisioningCard" aria-labelledby="provisioning-heading">
      <header className="dashCardHeader">
        <h2 id="provisioning-heading">Provisioning</h2>
        <span className="dashCardSubtitle">live pipeline steps</span>
      </header>
      <ol className="provisionStepsCard">
        {steps.map((step) => {
          const Icon = stepIcon[step.status];
          return (
            <li key={step.id} className={`provisionStepsCardItem ${step.status}`}>
              <Icon size={15} aria-hidden="true" />
              <span>{step.label}</span>
            </li>
          );
        })}
      </ol>
      {compact ? null : (
        <div className="boardsProgress">
          <div className="boardsProgressHeader">
            <span>Boards progress</span>
            <strong>{grouped.Done.length}/{totalItems} done</strong>
          </div>
          <div className="boardsProgressTrack">
            <div className="boardsProgressFill" style={{ width: `${donePercent}%` }} />
          </div>
          <div className="boardsProgressColumns">
            {kanbanColumns.map((column) => (
              <span key={column}>{column}: {grouped[column].length}</span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
