"""Application entrypoint for the PaperMinder websocket service."""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import init_db
from src.views.routes import router, ws_router


def create_app(*, database_url: str | None = None) -> FastAPI:
    init_db(database_url)

    app = FastAPI(
        title="PaperMinder Messaging Service",
        version="0.1.0",
        description="FastAPI application exposing websocket endpoints for personal messaging.",
    )

    # Configure CORS
    cors_env = os.getenv("CORS_ALLOWED_ORIGINS", "*")
    if cors_env.strip() == "*" or cors_env.strip() == "":
        allowed_origins = ["*"]
    else:
        allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.include_router(ws_router)
    return app


app = create_app()
