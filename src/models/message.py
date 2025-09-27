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
    message: str = Field(..., min_length=1, max_length=500, description="Body of the message to deliver")


class OutboundMessage(BaseModel):
    """Envelope for standard user-to-user messages delivered to websocket clients."""

    sender_name: str
    message: str = Field(..., max_length=500)
    timestamp: datetime = Field(default_factory=_utcnow)
    kind: Literal["message"] = "message"


class StatusMessage(BaseModel):
    """Payload used to communicate status updates or errors to a websocket client."""

    code: Literal["validation_error", "recipient_not_connected", "info", "subscription_accepted"]
    detail: str
    timestamp: datetime = Field(default_factory=_utcnow)
    kind: Literal["status"] = "status"


class TestMessageRequest(BaseModel):
    """Request body for sending a test message to a connected websocket user via HTTP."""

    recipient_id: UUID = Field(
        ..., description="Identifier of the user who should receive the test message"
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
