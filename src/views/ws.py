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
from src.models.firmware import (
    FirmwareDeclinedMessage,
    FirmwareProgressMessage,
    FirmwareCompleteMessage,
    FirmwareFailedMessage,
)
from src.crud import update_printer_connection_status


ws_router = APIRouter(tags=["websocket"])


@ws_router.websocket("/ws/{user_id}")
async def websocket_entrypoint(websocket: WebSocket, user_id: UUID) -> None:
    """WebSocket endpoint for real-time messaging and firmware updates."""
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

            # Handle printer subscription
            if {"printer_name", "printer_id"}.issubset(payload):
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

            # Handle firmware update messages from printers
            if payload.get("kind") in ["firmware_declined", "firmware_progress", "firmware_complete", "firmware_failed"]:
                await _handle_firmware_message(user_key, payload)
                continue

            # Handle regular messages
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
        # Update printer status to offline when disconnected
        import asyncio
        await asyncio.to_thread(
            update_printer_connection_status,
            uuid=user_key,
            online=False,
        )


async def _handle_firmware_message(printer_uuid: str, payload: dict) -> None:
    """Handle firmware update messages from printers.

    Args:
        printer_uuid: The printer UUID
        payload: The firmware message payload
    """
    message_kind = payload.get("kind")

    try:
        if message_kind == "firmware_declined":
            message = FirmwareDeclinedMessage.model_validate(payload)
            await connection_manager.handle_firmware_declined(
                printer_uuid=printer_uuid,
                version=message.version,
                auto_update=message.auto_update,
            )

        elif message_kind == "firmware_progress":
            message = FirmwareProgressMessage.model_validate(payload)
            await connection_manager.handle_firmware_progress(
                printer_uuid=printer_uuid,
                percent=message.percent,
                status_message=message.status,
            )

        elif message_kind == "firmware_complete":
            message = FirmwareCompleteMessage.model_validate(payload)
            await connection_manager.handle_firmware_complete(
                printer_uuid=printer_uuid,
                version=message.version,
            )

        elif message_kind == "firmware_failed":
            message = FirmwareFailedMessage.model_validate(payload)
            await connection_manager.handle_firmware_failed(
                printer_uuid=printer_uuid,
                error_message=message.error,
            )

    except ValidationError as exc:
        # Log validation error - can't send notification without websocket reference
        import logging
        logging.getLogger(__name__).error(f"Firmware message validation error: {exc}")
    except Exception as exc:
        # Log error but don't send notification to avoid infinite loop
        import logging
        logging.getLogger(__name__).exception(f"Failed to handle firmware message: {exc}")

