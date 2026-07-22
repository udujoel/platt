import React from "react";
import { Columns3 } from "lucide-react";
import { groupByColumn, kanbanColumns, useKanbanStore } from "./kanban-store";
import type { BackendEvent } from "../backend-events";

export function KanbanPanel({ open, onClose, lastEvent }: { open: boolean; onClose: () => void; lastEvent: BackendEvent | null }) {
  const items = useKanbanStore((store) => store.items);
  const applyEvent = useKanbanStore((store) => store.applyEvent);

  React.useEffect(() => {
    if (lastEvent) applyEvent(lastEvent);
  }, [applyEvent, lastEvent]);

  const grouped = groupByColumn(items);

  return (
    <section className={`slideOverPanel kanbanPanel ${open ? "open" : ""}`} aria-hidden={!open} aria-label="Kanban board">
      <header className="slideOverHeader">
        <div>
          <p className="eyebrow">Work items</p>
          <h1>Kanban</h1>
        </div>
        <button className="iconButton" type="button" onClick={onClose} aria-label="Close Kanban panel">
          &times;
        </button>
      </header>
      {items.length === 0 ? (
        <div className="emptyState">
          <Columns3 size={18} aria-hidden="true" />
          <strong>No work items yet</strong>
          <p>Cards created on Azure Boards will appear here as Platt moves them.</p>
        </div>
      ) : (
        <div className="kanbanColumns">
          {kanbanColumns.map((column) => (
            <div className="kanbanColumn" key={column}>
              <header>
                <span>{column}</span>
                <em>{grouped[column].length}</em>
              </header>
              <ol>
                {grouped[column].map((item) => (
                  <li key={item.id} className="kanbanCard">
                    <strong>{item.title}</strong>
                    <span>{item.id}</span>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
