import { describe, expect, it } from "vitest";

import { resolveBackendConfiguration } from "./backend-config";

describe("resolveBackendConfiguration", () => {
  it("keeps the local development defaults available", () => {
    expect(resolveBackendConfiguration({ frontendHostname: "127.0.0.1" })).toMatchObject({
      apiBaseUrl: "http://127.0.0.1:8000",
      wsUrl: "ws://127.0.0.1:8000/ws",
      isConfigured: true,
    });
  });

  it("blocks a hosted frontend from silently targeting local defaults", () => {
    const configuration = resolveBackendConfiguration({ frontendHostname: "platt.example.com" });

    expect(configuration.isConfigured).toBe(false);
    expect(configuration.message).toContain("VITE_API_BASE_URL");
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

  it("rejects unsupported endpoint protocols", () => {
    const configuration = resolveBackendConfiguration({
      frontendHostname: "platt.example.com",
      apiBaseUrl: "file:///private/api",
      wsUrl: "https://api.platt.example.com/ws",
    });

    expect(configuration.isConfigured).toBe(false);
    expect(configuration.message).toContain("http(s)");
  });
});
