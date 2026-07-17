from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.event_bus import event_bus
from app.persistence import Persistence
from app.routers import audit, chat, dev, health, jobs, ws


LOCAL_VITE_ORIGIN_REGEX = r"^http://(?:localhost|127\.0\.0\.1):517\d+$"


def create_app(db_path: str | Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        persistence = Persistence(db_path=db_path)
        recorder = persistence.record_event
        app.state.persistence = persistence
        event_bus.set_recorder(recorder)
        try:
            yield
        finally:
            event_bus.clear_recorder(recorder)
            persistence.close()

    app = FastAPI(title="Platt API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=LOCAL_VITE_ORIGIN_REGEX,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(dev.router)
    app.include_router(jobs.router)
    app.include_router(audit.router)
    app.include_router(ws.router)
    return app


app = create_app()
