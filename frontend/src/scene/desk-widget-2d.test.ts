import { describe, expect, it } from "vitest";

import { deskFallbackMonitorColor, deskFallbackStatusLabel } from "./desk-widget-2d";

describe("deskFallbackMonitorColor", () => {
  it("reads red for concerned", () => {
    expect(deskFallbackMonitorColor("concerned")).toBe("#f87171");
  });

  it("reads amber for working and thinking", () => {
    expect(deskFallbackMonitorColor("working")).toBe("#ffb454");
    expect(deskFallbackMonitorColor("thinking")).toBe("#ffb454");
  });

  it("reads teal for every other state", () => {
    for (const state of ["idle", "listening", "talking", "awaiting_approval", "celebrating"] as const) {
      expect(deskFallbackMonitorColor(state)).toBe("#2dd4bf");
    }
  });
});

describe("deskFallbackStatusLabel", () => {
  it("passes single-word states through unchanged", () => {
    expect(deskFallbackStatusLabel("idle")).toBe("idle");
    expect(deskFallbackStatusLabel("working")).toBe("working");
  });

  it("replaces underscores with spaces", () => {
    expect(deskFallbackStatusLabel("awaiting_approval")).toBe("awaiting approval");
  });
});
