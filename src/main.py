"""Application entrypoint for the PaperMinder websocket service."""

from __future__ import annotations

import os

from authx import AuthX, AuthXConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import init_db
from src.views import (
    health_router,
    printer_router,
    message_router,
    ws_router,
)


def create_app(*, database_url: str | None = None) -> FastAPI:
    init_db(database_url)

    app = FastAPI(
        title="PaperMinder Messaging Service",
        version="0.1.0",
        description="FastAPI application exposing websocket endpoints for personal messaging.",
    )

    auth_config = AuthXConfig(
        JWT_ALGORITHM = "HS256",
        JWT_SECRET_KEY = "4c0458b57f668d6059b261822b9c299240c8e1c4d86e70842ffeb0df42fab8b61cd67001b630394d4676808e0c841c76d14f838b06f59ed0a66b65172f56fa01883b2147a0d1153c35bdd3d6755ac1e9300619f5c469c2dcc9ec8366226e42f8f0d54b2da9ca1b2e129cd5c757f4459b9365f939c4af84ba039e95c47968cef5fca378fcfaed6d9fd3bb27948195171c9429eeb60f06ecbc03a29ba3cad8bfee4623328267043d7cb681f4127586fbef9c167e0c649d1056642a80208bdc20f5c00bf42b0fa8ff06571b34e2399c16d4b7c19c6d099c9c1698226abdcd49e5ec43e64cfd668e595368475d0675d92a1810edb978eb1bbd5f146d0b7512544b26",
        JWT_TOKEN_LOCATION = ["headers"],
    )

    auth = AuthX(config=auth_config)
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
    app.include_router(health_router)
    app.include_router(printer_router)
    app.include_router(message_router)
    app.include_router(ws_router)
    return app


app = create_app()
