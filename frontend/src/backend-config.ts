export type BackendConfiguration = {
  apiBaseUrl: string;
  wsUrl: string;
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
  const resolvedApiBaseUrl = apiBaseUrl ?? LOCAL_API_BASE_URL;
  const resolvedWsUrl = wsUrl ?? LOCAL_WS_URL;
  const endpointsAreValid =
    hasProtocol(resolvedApiBaseUrl, ["http:", "https:"]) &&
    hasProtocol(resolvedWsUrl, ["ws:", "wss:"]);
  const hostedWithoutEndpoints =
    !isLocalHostname(frontendHostname) && (!apiBaseUrl || !wsUrl);

  if (!endpointsAreValid) {
    return {
      apiBaseUrl: resolvedApiBaseUrl,
      wsUrl: resolvedWsUrl,
      isConfigured: false,
      message: "Set VITE_API_BASE_URL to an http(s) URL and VITE_WS_URL to a ws(s) URL.",
    };
  }

  if (hostedWithoutEndpoints) {
    const missingVariables = [
      apiBaseUrl ? null : "VITE_API_BASE_URL",
      wsUrl ? null : "VITE_WS_URL",
    ].filter((value): value is string => value !== null);

    return {
      apiBaseUrl: resolvedApiBaseUrl,
      wsUrl: resolvedWsUrl,
      isConfigured: false,
      message: `This hosted Platt build needs ${missingVariables.join(" and ")} before it can connect to a backend.`,
    };
  }

  return {
    apiBaseUrl: resolvedApiBaseUrl,
    wsUrl: resolvedWsUrl,
    isConfigured: true,
    message: null,
  };
}
