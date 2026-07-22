import { describe, expect, it } from "vitest";

import { closeActivePanel, toggleActivePanel } from "./panel-visibility";

describe("toggleActivePanel", () => {
  it("opens a panel when nothing is active", () => {
    expect(toggleActivePanel(null, "kanban")).toBe("kanban");
  });

  it("switches from one panel straight to another", () => {
    expect(toggleActivePanel("kanban", "dashboard")).toBe("dashboard");
  });

  it("closes the active panel when it is clicked again", () => {
    expect(toggleActivePanel("kanban", "kanban")).toBeNull();
  });
});

describe("closeActivePanel", () => {
  it("clears the panel when it is the one currently active", () => {
    expect(closeActivePanel("kanban", "kanban")).toBeNull();
  });

  it("leaves a different active panel untouched — the MAJOR CodeRabbit fix: a stale close must not close the wrong panel", () => {
    // e.g. Kanban's onClose fires after the operator already switched to Dashboard.
    expect(closeActivePanel("dashboard", "kanban")).toBe("dashboard");
  });

  it("is a no-op when nothing is active", () => {
    expect(closeActivePanel(null, "kanban")).toBeNull();
  });
});
