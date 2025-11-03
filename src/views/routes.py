"""Router definitions for HTTP and websocket endpoints.

This module consolidates all routers from different route types and includes them
in the main application.
"""

from src.views import health_routes, printer_routes, message_routes

# Import routers
health_router = health_routes.router
printer_router = printer_routes.router
message_router = message_routes.router
ws_router = message_routes.ws_router

__all__ = [
    "health_router",
    "printer_router",
    "message_router",
    "ws_router",
]
