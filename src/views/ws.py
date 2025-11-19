from __future__ import annotations
import json
from json import JSONDecodeError
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from pydantic import ValidationError
from src.controllers.message_controller import connection_manager, RecipientNotConnectedError
from src.models.message import (
    InboundMessage,
    StatusMessage,
    SubscriptionRequest
)


ws_router = APIRouter(tags=["websocket"])


@ws_router.websocket("/ws/{user_id}")
async def websocket_entrypoint(websocket: WebSocket, user_id: UUID) -> None:
    """WebSocket endpoint for real-time messaging."""
    user_key = str(user_id)
    await connection_manager.connect(user_key, websocket)
    await connection_manager.notify(
        websocket,
        StatusMessage(code="info", detail="connected"),
    )
    
    # Send any cached messages the user may have missed while offline
    await connection_manager.send_cached_messages(user_key, websocket)

    try:
        while True:
            raw_payload = await websocket.receive_text()
            try:
                payload = json.loads(raw_payload)
            except JSONDecodeError as exc:
                await connection_manager.notify(
                    websocket,
                    StatusMessage(code="validation_error", detail=f"Invalid JSON payload: {exc}"),
                )
                continue

            if not isinstance(payload, dict):
                await connection_manager.notify(
                    websocket,
                    StatusMessage(code="validation_error", detail="Payload must be a JSON object."),
                )
                continue

            if {"printer_name", "api_key"}.issubset(payload):
                try:
                    subscription = SubscriptionRequest.model_validate(payload)
                except ValidationError as exc:
                    await connection_manager.notify(
                        websocket,
                        StatusMessage(code="validation_error", detail=str(exc)),
                    )
                    continue

                await connection_manager.register_subscription(websocket, subscription)
                await connection_manager.notify(
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
                await connection_manager.notify(
                    websocket,
                    StatusMessage(code="validation_error", detail=str(exc)),
                )
                continue

            try:
                await connection_manager.send_personal_message(sender_id=user_key, message=message)
            except RecipientNotConnectedError:
                await connection_manager.notify(
                    websocket,
                    StatusMessage(
                        code="recipient_not_connected",
                        detail=f"Recipient '{message.recipient_id}' is not connected.",
                    ),
                )
    except WebSocketDisconnect:
        await connection_manager.disconnect(user_key, websocket)
