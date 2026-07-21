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

  it("defaults a hosted frontend to the same-origin /api backend when no URL is set", () => {
    const configuration = resolveBackendConfiguration({ frontendHostname: "platt.example.com" });

    expect(configuration).toMatchObject({
      apiBaseUrl: "https://platt.example.com/api",
      wsUrl: null,
      isConfigured: true,
      message: null,
    });
  });

  it("considers a hosted frontend configured with only VITE_API_BASE_URL, using SSE with no WS URL", () => {
    const configuration = resolveBackendConfiguration({
      frontendHostname: "platt.example.com",
      apiBaseUrl: "https://api.platt.example.com",
    });

    expect(configuration).toMatchObject({
      apiBaseUrl: "https://api.platt.example.com",
      wsUrl: null,
      isConfigured: true,
      message: null,
    });
  });

  it("uses same-origin /api and the explicit WS URL when only VITE_WS_URL is set", () => {
    const configuration = resolveBackendConfiguration({
      frontendHostname: "platt.example.com",
      wsUrl: "wss://api.platt.example.com/ws",
    });

    expect(configuration).toMatchObject({
      apiBaseUrl: "https://platt.example.com/api",
      wsUrl: "wss://api.platt.example.com/ws",
      isConfigured: true,
      message: null,
    });
  });

  it("accepts an explicitly configured hosted backend with both URLs", () => {
    expect(
      resolveBackendConfiguration({
        frontendHostname: "platt.example.com",
        apiBaseUrl: "https://api.platt.example.com",
        wsUrl: "wss://api.platt.example.com/ws",
      }),
    ).toMatchObject({ isConfigured: true, wsUrl: "wss://api.platt.example.com/ws", message: null });
  });

  it("rejects an unsupported API protocol", () => {
    const configuration = resolveBackendConfiguration({
      frontendHostname: "platt.example.com",
      apiBaseUrl: "file:///private/api",
    });

    expect(configuration.isConfigured).toBe(false);
    expect(configuration.message).toContain("http(s)");
  });

  it("rejects an unsupported WebSocket protocol when VITE_WS_URL is set", () => {
    const configuration = resolveBackendConfiguration({
      frontendHostname: "platt.example.com",
      apiBaseUrl: "https://api.platt.example.com",
      wsUrl: "https://api.platt.example.com/ws",
    });

    expect(configuration.isConfigured).toBe(false);
    expect(configuration.message).toContain("ws(s)");
  });
});
