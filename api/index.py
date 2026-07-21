"""Vercel Python Function entrypoint: exposes the FastAPI backend under /api.

Vercel builds every file in api/** as an independent serverless function and
imports it with the project root as the working directory, so `backend/` is
not on `sys.path` by default. We add it before importing the app package.

The FastAPI app in backend/app/main.py registers routes without an /api
prefix (matching the local `uvicorn` dev server), so it is mounted under
/api here rather than modified. Starlette's Mount strips the /api prefix
from the incoming ASGI scope before dispatching, so app.main's route
definitions and local-dev behavior stay unchanged. vercel.json rewrites
every /api/* request to this file, and Vercel rewrites preserve the
original request path, so the mount point must match the public prefix.
"""

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from fastapi import FastAPI  # noqa: E402

from app.main import app as backend_app  # noqa: E402

app = FastAPI()
app.mount("/api", backend_app)
