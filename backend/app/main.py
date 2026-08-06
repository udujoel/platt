import asyncio
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.background_tasks import cancel_background_tasks
from app.collectors import DashboardCache
from app.event_bus import event_bus
from app.persistence import Persistence
from app.routers import (
    approvals,
    audit,
    chat,
    dashboard,
    dev,
    events,
    health,
    jobs,
    onboarding,
    provision,
    sse,
    version_bump,
    ws,
)


LOCAL_VITE_ORIGIN_REGEX = r"^http://(?:localhost|127\.0\.0\.1):517\d+$"
ALLOWED_ORIGIN_REGEX_ENV = "PLATT_ALLOWED_ORIGIN_REGEX"


def resolve_allowed_origin_regex(configured_regex: str | None = None) -> str:
    """Return a validated CORS policy without broadening the local default.

    Operators should use simple, anchored expressions because CORS evaluates the
    policy on every browser preflight request.
    """

    origin_regex = (
        configured_regex
        if configured_regex is not None
        else os.environ.get(ALLOWED_ORIGIN_REGEX_ENV, LOCAL_VITE_ORIGIN_REGEX)
    )
    if not origin_regex:
        raise ValueError(f"{ALLOWED_ORIGIN_REGEX_ENV} must not be empty")

    try:
        re.compile(origin_regex)
    except re.error as error:
        raise ValueError(
            f"{ALLOWED_ORIGIN_REGEX_ENV} must be a valid regular expression"
        ) from error
    return origin_regex


def create_app(
    db_path: str | Path | None = None,
    allowed_origin_regex: str | None = None,
    database_url: str | None = None,
) -> FastAPI:
    persistence = Persistence(db_path=db_path, database_url=database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        recorder = persistence.record_event
        app.state.background_tasks: set[asyncio.Task[Any]] = set()
        event_bus.set_recorder(recorder)
        try:
            yield
        finally:
            await cancel_background_tasks(app.state.background_tasks)
            event_bus.clear_recorder(recorder)
            persistence.close()

    origin_regex = resolve_allowed_origin_regex(allowed_origin_regex)
    app = FastAPI(title="Platt API", version="0.1.0", lifespan=lifespan)
    app.state.persistence = persistence
    app.state.allowed_origin_regex = origin_regex
    app.state.allowed_origin_pattern = re.compile(origin_regex)
    # Disposable plan->apply handoff scratch state (see app/routers/provision.py);
    # the approval itself, not this dict, is the durable authorization record.
    app.state.provision_jobs: dict[Any, dict[str, Any]] = {}
    app.state.provision_repository_id = os.environ.get("PLATT_PROVISION_REPOSITORY_ID", "")
    apply_pipeline_id = os.environ.get("PLATT_PROVISION_APPLY_PIPELINE_ID", "").strip()
    app.state.provision_apply_pipeline_id = int(apply_pipeline_id) if apply_pipeline_id else None
    app.state.dashboard_cache = DashboardCache()
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=origin_regex,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(dev.router)
    app.include_router(jobs.router)
    app.include_router(events.router)
    app.include_router(sse.router)
    app.include_router(audit.router)
    app.include_router(onboarding.router)
    app.include_router(approvals.router)
    app.include_router(dashboard.router)
    app.include_router(provision.router)
    app.include_router(version_bump.router)
    app.include_router(ws.router)
    return app


app = create_app()
