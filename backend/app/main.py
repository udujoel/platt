from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.event_bus import event_bus
from app.persistence import Persistence
from app.routers import audit, chat, dev, health, jobs, ws


def create_app(db_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(title="Platt API", version="0.1.0")
    persistence = Persistence(db_path=db_path)
    event_bus.set_recorder(persistence.record_event)
    app.state.persistence = persistence

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5173",
            "http://localhost:5174",
        ],
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
