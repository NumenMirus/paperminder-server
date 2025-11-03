"""Health check routes."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health probe for monitoring."""

    return {"status": "ok"}
