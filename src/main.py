"""Application entrypoint for the PaperMinder websocket service."""

from fastapi import FastAPI

from src.views.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="PaperMinder Messaging Service",
        version="0.1.0",
        description="FastAPI application exposing websocket endpoints for personal messaging.",
    )
    app.include_router(router)
    return app


app = create_app()
