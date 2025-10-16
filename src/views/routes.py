"""Router definitions for HTTP and websocket endpoints."""

from __future__ import annotations

import json
from json import JSONDecodeError
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.controllers.message_controller import ConnectionManager, RecipientNotConnectedError
from src.models.message import InboundMessage, StatusMessage, SubscriptionRequest, TestMessageRequest

router = APIRouter(prefix="/api")

_manager = ConnectionManager()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health probe for monitoring."""

    return {"status": "ok"}


@router.post("/messages", status_code=status.HTTP_202_ACCEPTED)
async def send_test_message(payload: TestMessageRequest) -> dict[str, str]:
    """HTTP endpoint to deliver a test message to a connected websocket client."""

    inbound = InboundMessage(
        recipient_id=payload.recipient_id,
        sender_name=payload.sender_name,
        message=payload.message,
    )
    try:
        await _manager.send_personal_message(sender_id=payload.sender_name, message=inbound)
    except RecipientNotConnectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient '{payload.recipient_id}' is not connected.",
        ) from exc

    return {"status": "sent"}


@router.websocket("/ws/{user_id}")
async def websocket_entrypoint(websocket: WebSocket, user_id: UUID) -> None:
    user_key = str(user_id)
    await _manager.connect(user_key, websocket)
    await _manager.notify(
        websocket,
        StatusMessage(code="info", detail="connected"),
    )

    try:
        while True:
            raw_payload = await websocket.receive_text()
            try:
                payload = json.loads(raw_payload)
            except JSONDecodeError as exc:
                await _manager.notify(
                    websocket,
                    StatusMessage(code="validation_error", detail=f"Invalid JSON payload: {exc}"),
                )
                continue

            if not isinstance(payload, dict):
                await _manager.notify(
                    websocket,
                    StatusMessage(code="validation_error", detail="Payload must be a JSON object."),
                )
                continue

            if {"printer_name", "api_key"}.issubset(payload):
                try:
                    subscription = SubscriptionRequest.model_validate(payload)
                except ValidationError as exc:
                    await _manager.notify(
                        websocket,
                        StatusMessage(code="validation_error", detail=str(exc)),
                    )
                    continue

                await _manager.register_subscription(websocket, subscription)
                await _manager.notify(
                    websocket,
                    StatusMessage(
                        code="subscription_accepted",
                        detail=f"Printer '{subscription.printer_name}' subscribed successfully.",
                    ),
                )
                continue

            try:
                message = InboundMessage.model_validate(payload)
            except ValidationError as exc:
                await _manager.notify(
                    websocket,
                    StatusMessage(code="validation_error", detail=str(exc)),
                )
                continue

            try:
                await _manager.send_personal_message(sender_id=user_key, message=message)
            except RecipientNotConnectedError:
                await _manager.notify(
                    websocket,
                    StatusMessage(
                        code="recipient_not_connected",
                        detail=f"Recipient '{message.recipient_id}' is not connected.",
                    ),
                )
    except WebSocketDisconnect:
        await _manager.disconnect(user_key, websocket)
