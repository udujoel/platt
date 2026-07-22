import React from "react";
import { ClipboardList, Columns3, LayoutDashboard } from "lucide-react";

export type RailPanel = "kanban" | "dashboard" | "audit";

export function IconRail({ active, onSelect }: { active: RailPanel | null; onSelect: (panel: RailPanel) => void }) {
  return (
    <nav className="iconRail" aria-label="Panels">
      <button
        type="button"
        className={active === "kanban" ? "active" : ""}
        onClick={() => onSelect("kanban")}
        aria-pressed={active === "kanban"}
        title="Kanban"
      >
        <Columns3 size={20} aria-hidden="true" />
      </button>
      <button
        type="button"
        className={active === "dashboard" ? "active" : ""}
        onClick={() => onSelect("dashboard")}
        aria-pressed={active === "dashboard"}
        title="Dashboard"
      >
        <LayoutDashboard size={20} aria-hidden="true" />
      </button>
      <button
        type="button"
        className={active === "audit" ? "active" : ""}
        onClick={() => onSelect("audit")}
        aria-pressed={active === "audit"}
        title="Audit"
      >
        <ClipboardList size={20} aria-hidden="true" />
      </button>
    </nav>
  );
}
