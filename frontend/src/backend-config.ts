export type BackendConfiguration = {
  apiBaseUrl: string;
  wsUrl: string | null;
  isConfigured: boolean;
  message: string | null;
};

type BackendConfigurationInput = {
  apiBaseUrl?: string;
  frontendHostname: string;
  wsUrl?: string;
};

const LOCAL_API_BASE_URL = "http://127.0.0.1:8000";
const LOCAL_WS_URL = "ws://127.0.0.1:8000/ws";

function hasProtocol(value: string, allowedProtocols: string[]) {
  try {
    return allowedProtocols.includes(new URL(value).protocol);
  } catch {
    return false;
  }
}

function isLocalHostname(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

export function resolveBackendConfiguration({
  apiBaseUrl,
  frontendHostname,
  wsUrl,
}: BackendConfigurationInput): BackendConfiguration {
  const isLocal = isLocalHostname(frontendHostname);
  const resolvedApiBaseUrl = apiBaseUrl ?? LOCAL_API_BASE_URL;
  // VITE_WS_URL is optional: hosted builds use SSE by default and only fall
  // back to a WebSocket transport when a ws(s) URL is explicitly configured.
  const resolvedWsUrl = wsUrl ?? (isLocal ? LOCAL_WS_URL : null);

  const apiBaseUrlIsValid = hasProtocol(resolvedApiBaseUrl, ["http:", "https:"]);
  const wsUrlIsValid = resolvedWsUrl === null || hasProtocol(resolvedWsUrl, ["ws:", "wss:"]);

  if (!apiBaseUrlIsValid || !wsUrlIsValid) {
    return {
      apiBaseUrl: resolvedApiBaseUrl,
      wsUrl: resolvedWsUrl,
      isConfigured: false,
      message: "Set VITE_API_BASE_URL to an http(s) URL and, if set, VITE_WS_URL to a ws(s) URL.",
    };
  }

  if (!isLocal && !apiBaseUrl) {
    return {
      apiBaseUrl: resolvedApiBaseUrl,
      wsUrl: resolvedWsUrl,
      isConfigured: false,
      message: "This hosted Platt build needs VITE_API_BASE_URL before it can connect to a backend.",
    };
  }

  return {
    apiBaseUrl: resolvedApiBaseUrl,
    wsUrl: resolvedWsUrl,
    isConfigured: true,
    message: null,
  };
}
