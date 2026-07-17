# Development

Use Node 20+ and Python 3.12. The backend and frontend are intentionally separate so Vercel can host the browser app while the API can run on an appropriate Python host.

Phase 1 uses a real Anthropic streaming client when `ANTHROPIC_API_KEY` is available. When it is absent, `/chat` streams a clear configuration error and returns Platt to idle; use `/dev/state-cycle` to exercise every state without provider credentials. `PLATT_ANTHROPIC_MODEL` defaults to `claude-sonnet-4-6` and can be overridden for a compatible Anthropic model.

Do not add Azure credentials or apply credentials to local development files.
