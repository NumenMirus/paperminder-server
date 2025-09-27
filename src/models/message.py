"""Pydantic models that describe inbound and outbound websocket payloads."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InboundMessage(BaseModel):
    """Message schema for data sent by a websocket client."""

    recipient_id: str = Field(..., min_length=1, description="Identifier of the intended recipient")
    content: str = Field(..., min_length=1, max_length=2000, description="Body of the message")


class OutboundMessage(BaseModel):
    """Envelope for standard user-to-user messages delivered to websocket clients."""

    sender_id: str
    recipient_id: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    kind: Literal["message"] = "message"


class StatusMessage(BaseModel):
    """Payload used to communicate status updates or errors to a websocket client."""

    code: Literal["validation_error", "recipient_not_connected", "info", "subscription_accepted"]
    detail: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    kind: Literal["status"] = "status"


class TestMessageRequest(BaseModel):
    """Request body for sending a test message to a connected websocket user via HTTP."""

    recipient_id: str = Field(
        ..., min_length=1, description="Identifier of the user who should receive the test message"
    )
    content: str = Field(
        ..., min_length=1, max_length=2000, description="Body of the test message to deliver"
    )
    sender_id: str = Field(
        default="test",
        min_length=1,
        description="Identifier to include as the sender in the delivered message",
    )


class SubscriptionRequest(BaseModel):
    """Payload used by printers to subscribe to websocket updates."""

    printer_name: str = Field(..., min_length=1, description="Human readable printer identifier")
    api_key: str = Field(..., min_length=1, description="API key used to authorise the printer subscription")
