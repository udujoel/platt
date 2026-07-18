import { describe, expect, it } from "vitest";

import { parseBackendReadiness } from "./readiness-status";

describe("parseBackendReadiness", () => {
  it("recognizes the verified readiness contract", () => {
    expect(parseBackendReadiness({ status: "ready", persistence: "ok" })).toBe("ready");
  });

  it("treats missing or malformed readiness payloads as unavailable", () => {
    expect(parseBackendReadiness({ status: "ready" })).toBe("unavailable");
    expect(parseBackendReadiness({ status: "ok", persistence: "ok" })).toBe("unavailable");
    expect(parseBackendReadiness(null)).toBe("unavailable");
  });
});
