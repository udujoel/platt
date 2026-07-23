import React from "react";
import { Columns3 } from "lucide-react";
import { groupByColumn, kanbanColumns, useKanbanStore } from "./kanban-store";
import type { BackendEvent } from "../backend-events";

export function BoardsBoard({ lastEvent }: { lastEvent: BackendEvent | null }) {
  const items = useKanbanStore((store) => store.items);
  const applyEvent = useKanbanStore((store) => store.applyEvent);

  React.useEffect(() => {
    if (lastEvent) applyEvent(lastEvent);
  }, [applyEvent, lastEvent]);

  const grouped = groupByColumn(items);

  return (
    <section className="dashCard boardsBoardCard" aria-labelledby="boards-heading">
      <header className="dashCardHeader">
        <h2 id="boards-heading">Boards</h2>
        <span className="dashCardSubtitle">{items.length} work items</span>
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
