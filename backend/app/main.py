from fastapi import FastAPI

from app.routers import chat, health, ws


def create_app() -> FastAPI:
    app = FastAPI(title="Platt API", version="0.1.0")
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(ws.router)
    return app


app = create_app()

