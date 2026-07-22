import { create } from "zustand";
import type { BackendEvent } from "../backend-events";

export type KanbanColumn = "To Do" | "Doing" | "Done";

export type WorkItem = {
  id: string;
  jobId: string;
  title: string;
  column: KanbanColumn;
  updatedAt: string;
};

type WorkItemMovedLike = {
  work_item_id: string;
  job_id: string;
  title: string;
  to_state: string;
  created_at: string;
};

/**
 * Azure Boards state names vary by process template (Basic vs Agile vs
 * Scrum), so this buckets on substring rather than an exact enum match.
 */
export function classifyColumn(toState: string): KanbanColumn {
  const normalized = toState.trim().toLowerCase();
  if (["done", "closed", "resolved", "completed"].some((marker) => normalized.includes(marker))) return "Done";
  if (["doing", "active", "progress", "committed", "review"].some((marker) => normalized.includes(marker))) return "Doing";
  return "To Do";
}

export function applyWorkItemMoved(items: WorkItem[], event: WorkItemMovedLike): WorkItem[] {
  const next: WorkItem = {
    id: event.work_item_id,
    jobId: event.job_id,
    title: event.title,
    column: classifyColumn(event.to_state),
    updatedAt: event.created_at,
  };

  const existingIndex = items.findIndex((item) => item.id === next.id);
  if (existingIndex === -1) return [...items, next];

  const copy = items.slice();
  copy[existingIndex] = next;
  return copy;
}

export const kanbanColumns: KanbanColumn[] = ["To Do", "Doing", "Done"];

export function groupByColumn(items: WorkItem[]): Record<KanbanColumn, WorkItem[]> {
  const grouped: Record<KanbanColumn, WorkItem[]> = { "To Do": [], Doing: [], Done: [] };
  for (const item of items) grouped[item.column].push(item);
  return grouped;
}

type KanbanStore = {
  items: WorkItem[];
  seenEventIds: string[];
  applyEvent: (event: BackendEvent) => void;
};

export const useKanbanStore = create<KanbanStore>((set) => ({
  items: [],
  seenEventIds: [],
  applyEvent: (event) =>
    set((current) => {
      if (event.type !== "work_item_moved") return current;
      if (current.seenEventIds.includes(event.id)) return current;
      return {
        items: applyWorkItemMoved(current.items, event),
        seenEventIds: [...current.seenEventIds, event.id].slice(-500),
      };
    }),
}));
