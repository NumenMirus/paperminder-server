"""Pydantic models for bitmap printing messages."""

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class PrintBitmapMessage(BaseModel):
    """Message sent from server to printer to print a bitmap image."""

    kind: Literal["print_bitmap"] = "print_bitmap"
    width: int = Field(..., description="Image width in pixels (must be multiple of 8)", gt=0)
    height: int = Field(..., description="Image height in pixels", gt=0)
    data: str = Field(..., description="Base64-encoded raw bitmap data")
    caption: str | None = Field(None, description="Optional caption text to print below image")


class BitmapPrintingMessage(BaseModel):
    """Success response sent from printer to server after receiving bitmap."""

    kind: Literal["bitmap_printing"] = "bitmap_printing"
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")


class BitmapErrorMessage(BaseModel):
    """Error response sent from printer to server if bitmap printing fails."""

    kind: Literal["bitmap_error"] = "bitmap_error"
    error: str = Field(
        ...,
        description="Error message describing what went wrong",
    )
