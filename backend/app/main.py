from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import chat, dev, health, ws


def create_app() -> FastAPI:
    app = FastAPI(title="Platt API", version="0.1.0")
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
    app.include_router(ws.router)
    return app


app = create_app()
