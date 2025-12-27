from __future__ import annotations
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.views import (
    auth_router,
    health_router,
    printer_router,
    message_router,
    ws_router,
    firmware_router,
)

from src.config import auth, configure_logging

def create_app(*, database_url: str | None = None) -> FastAPI:
    # Configure logging first
    configure_logging()

    # Initialize database connection on startup
    # Tables are created by migrations, not by init_db
    from src.database import configure_database
    configure_database(database_url)

    app = FastAPI(
        title="PaperMinder Messaging Service",
        version="1.1.0",
        description="PaperMinder FastAPI application exposing websocket endpoints for personal messaging and firmware updates.",
    )

    auth.handle_errors(app)

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

    # Include all routers by type
    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(printer_router)
    app.include_router(message_router)
    app.include_router(ws_router)
    app.include_router(firmware_router)

    return app


app = create_app()
