import { describe, expect, it } from "vitest";

import { applyWorkItemMoved, classifyColumn, groupByColumn } from "./kanban-store";
import type { WorkItem } from "./kanban-store";

describe("classifyColumn", () => {
  it("maps Azure Boards state names to the three Kanban columns", () => {
    expect(classifyColumn("New")).toBe("To Do");
    expect(classifyColumn("To Do")).toBe("To Do");
    expect(classifyColumn("Doing")).toBe("Doing");
    expect(classifyColumn("In Progress")).toBe("Doing");
    expect(classifyColumn("Code Review")).toBe("Doing");
    expect(classifyColumn("Done")).toBe("Done");
    expect(classifyColumn("Closed")).toBe("Done");
  });
});

describe("applyWorkItemMoved", () => {
  const baseEvent = {
    work_item_id: "wi-1",
    job_id: "job-1",
    title: "Create storage account",
    to_state: "Doing",
    created_at: "2026-07-22T00:00:00Z",
  };

  it("inserts a new work item on first sight", () => {
    const items = applyWorkItemMoved([], baseEvent);
    expect(items).toEqual([
      { id: "wi-1", jobId: "job-1", title: "Create storage account", column: "Doing", updatedAt: "2026-07-22T00:00:00Z" },
    ]);
  });

  it("updates the column in place when the same work item moves again", () => {
    const first = applyWorkItemMoved([], baseEvent);
    const second = applyWorkItemMoved(first, { ...baseEvent, to_state: "Done", created_at: "2026-07-22T00:05:00Z" });

    expect(second).toHaveLength(1);
    expect(second[0].column).toBe("Done");
    expect(second[0].updatedAt).toBe("2026-07-22T00:05:00Z");
  });

  it("keeps unrelated work items untouched", () => {
    const items: WorkItem[] = [{ id: "wi-2", jobId: "job-1", title: "Other task", column: "To Do", updatedAt: "t" }];
    const next = applyWorkItemMoved(items, baseEvent);
    expect(next).toHaveLength(2);
    expect(next.find((item) => item.id === "wi-2")?.column).toBe("To Do");
  });
});

describe("groupByColumn", () => {
  it("buckets items into all three columns, including empty ones", () => {
    const items: WorkItem[] = [
      { id: "wi-1", jobId: "job-1", title: "A", column: "To Do", updatedAt: "t" },
      { id: "wi-2", jobId: "job-1", title: "B", column: "Done", updatedAt: "t" },
    ];
    const grouped = groupByColumn(items);
    expect(grouped["To Do"]).toHaveLength(1);
    expect(grouped.Doing).toHaveLength(0);
    expect(grouped.Done).toHaveLength(1);
  });
});
