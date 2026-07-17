import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.background_tasks import cancel_background_tasks
from app.event_bus import event_bus
from app.persistence import Persistence
from app.routers import audit, chat, dev, health, jobs, onboarding, ws
from app.services.onboarding import OnboardingStore


LOCAL_VITE_ORIGIN_REGEX = r"^http://(?:localhost|127\.0\.0\.1):517\d+$"


def create_app(
    db_path: str | Path | None = None,
    onboarding_db_path: Path | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        persistence = Persistence(db_path=db_path)
        recorder = persistence.record_event
        app.state.persistence = persistence
        app.state.background_tasks: set[asyncio.Task[Any]] = set()
        event_bus.set_recorder(recorder)
        try:
            yield
        finally:
            await cancel_background_tasks(app.state.background_tasks)
            event_bus.clear_recorder(recorder)
            persistence.close()

    app = FastAPI(title="Platt API", version="0.1.0", lifespan=lifespan)
    app.state.onboarding_store = OnboardingStore(onboarding_db_path)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LOCAL_VITE_ORIGIN_REGEX,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(dev.router)
    app.include_router(jobs.router)
    app.include_router(audit.router)
    app.include_router(onboarding.router)
    app.include_router(ws.router)
    return app


app = create_app()
