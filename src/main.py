"""Application entrypoint for the PaperMinder websocket service."""

from __future__ import annotations

from fastapi import FastAPI

from src.database import init_db
from src.views.routes import router


def create_app(*, database_url: str | None = None) -> FastAPI:
    init_db(database_url)

    app = FastAPI(
        title="PaperMinder Messaging Service",
        version="0.1.0",
        description="FastAPI application exposing websocket endpoints for personal messaging.",
    )
    app.include_router(router)
    return app


app = create_app()
