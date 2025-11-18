"""Pydantic models that describe inbound and outbound websocket payloads."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class InboundMessage(BaseModel):
    """Message schema for data sent by a websocket client."""

    recipient_id: UUID = Field(..., description="Identifier of the intended recipient")
    sender_name: str = Field(..., min_length=1, description="Display name of the sender")
    message: str = Field(..., min_length=1, max_length=512, description="Body of the message to deliver")
    kind: Literal["message"] = "message"


class OutboundMessage(BaseModel):
    """Envelope for standard user-to-user messages delivered to websocket clients."""

    sender_name: str
    message: str = Field(..., max_length=500)
    timestamp: datetime = Field(default_factory=_utcnow)
    kind: Literal["message", "bitmap"] = "message"
    daily_number: int = Field(..., description="Progressive message number that resets daily for the recipient")


class StatusMessage(BaseModel):
    """Payload used to communicate status updates or errors to a websocket client."""

    code: Literal["validation_error", "recipient_not_connected", "info", "subscription_accepted"]
    detail: str
    timestamp: datetime = Field(default_factory=_utcnow)
    kind: Literal["status"] = "status"


class MessageRequest(BaseModel):
    """Request body for sending a test message to a connected websocket user via HTTP."""

    recipient_id: UUID = Field(
        ..., description="Identifier of the printer/user who should receive the test message"
    )
    sender_uuid: UUID = Field(
        ..., description="UUID of the user sending the message (must be printer owner or in same group)"
    )
    sender_name: str = Field(
        default="system",
        min_length=1,
        description="Display name to include as the sender in the delivered message",
    )
    message: str = Field(
        ..., min_length=1, max_length=500, description="Body of the test message to deliver"
    )


class SubscriptionRequest(BaseModel):
    """Payload used by printers to subscribe to websocket updates."""

    printer_name: str = Field(..., min_length=1, description="Human readable printer identifier")
    api_key: str = Field(..., min_length=1, description="API key used to authorise the printer subscription")


class PrinterRegistrationRequest(BaseModel):
    """Request body for registering a new printer."""

    name: str = Field(..., min_length=1, max_length=128, description="Name of the printer")
    uuid: UUID = Field(..., description="Unique identifier for the printer")
    location: str = Field(..., min_length=1, max_length=256, description="Physical location of the printer")
    user_uuid: UUID = Field(..., description="UUID of the user who owns the printer")


class PrinterRegistrationResponse(BaseModel):
    """Response after successfully registering a printer."""

    id: int = Field(..., description="Database ID of the registered printer")
    name: str
    uuid: UUID
    location: str
    user_uuid: UUID
    created_at: datetime

class PrinterResponse(BaseModel):
    """Response model for a registered printer."""

    id: int
    name: str
    uuid: UUID
    location: str