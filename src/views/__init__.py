"""View layer (routing) for PaperMinder messaging service."""


from .health import router as health_router
from .printer import router as printer_router
from .message import router as message_router
from .ws import ws_router
from .auth import router as auth_router


__all__ = [
    "health_router",
    "printer_router",
    "message_router",
    "ws_router",
    "auth_router",
]
