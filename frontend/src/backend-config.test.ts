import { describe, expect, it } from "vitest";

import { resolveBackendConfiguration } from "./backend-config";

describe("resolveBackendConfiguration", () => {
  it.each(["127.0.0.1", "localhost", "::1"])("keeps local development defaults available for %s", (frontendHostname) => {
    expect(resolveBackendConfiguration({ frontendHostname })).toMatchObject({
      apiBaseUrl: "http://127.0.0.1:8000",
      wsUrl: "ws://127.0.0.1:8000/ws",
      isConfigured: true,
      message: null,
    });
  });

  it("blocks a hosted frontend from silently targeting local defaults", () => {
    const configuration = resolveBackendConfiguration({ frontendHostname: "platt.example.com" });

    expect(configuration.isConfigured).toBe(false);
    expect(configuration.message).toContain("VITE_API_BASE_URL");
    expect(configuration.message).toContain("VITE_WS_URL");
  });

  it.each([
    {
      name: "API URL",
      configuration: { apiBaseUrl: "https://api.platt.example.com" },
      missingVariable: "VITE_WS_URL",
    },
    {
      name: "WebSocket URL",
      configuration: { wsUrl: "wss://api.platt.example.com/ws" },
      missingVariable: "VITE_API_BASE_URL",
    },
  ])("blocks a hosted frontend with only an $name", ({ configuration, missingVariable }) => {
    const resolved = resolveBackendConfiguration({
      frontendHostname: "platt.example.com",
      ...configuration,
    });

    expect(resolved.isConfigured).toBe(false);
    expect(resolved.message).toContain(missingVariable);
  });

  it("accepts an explicitly configured hosted backend", () => {
    expect(
      resolveBackendConfiguration({
        frontendHostname: "platt.example.com",
        apiBaseUrl: "https://api.platt.example.com",
        wsUrl: "wss://api.platt.example.com/ws",
      }),
    ).toMatchObject({ isConfigured: true, message: null });
  });

  it("rejects an unsupported API protocol", () => {
    const configuration = resolveBackendConfiguration({
      frontendHostname: "platt.example.com",
      apiBaseUrl: "file:///private/api",
      wsUrl: "wss://api.platt.example.com/ws",
    });

    expect(configuration.isConfigured).toBe(false);
    expect(configuration.message).toContain("http(s)");
  });

  it("rejects an unsupported WebSocket protocol", () => {
    const configuration = resolveBackendConfiguration({
      frontendHostname: "platt.example.com",
      apiBaseUrl: "https://api.platt.example.com",
      wsUrl: "https://api.platt.example.com/ws",
    });

    expect(configuration.isConfigured).toBe(false);
    expect(configuration.message).toContain("ws(s)");
  });
});
