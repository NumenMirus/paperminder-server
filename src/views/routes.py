"""Router definitions for HTTP and websocket endpoints."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from src.controllers.message_controller import ConnectionManager, RecipientNotConnectedError
from src.models.message import InboundMessage, StatusMessage

router = APIRouter()

_manager = ConnectionManager()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health probe for monitoring."""

    return {"status": "ok"}


@router.websocket("/ws/{user_id}")
async def websocket_entrypoint(websocket: WebSocket, user_id: str) -> None:
    await _manager.connect(user_id, websocket)
    await _manager.notify(
        websocket,
        StatusMessage(code="info", detail="connected"),
    )

    try:
        while True:
            raw_payload = await websocket.receive_text()
            try:
                message = InboundMessage.model_validate_json(raw_payload)
            except ValidationError as exc:
                await _manager.notify(
                    websocket,
                    StatusMessage(code="validation_error", detail=str(exc)),
                )
                continue

            try:
                await _manager.send_personal_message(sender_id=user_id, message=message)
            except RecipientNotConnectedError:
                await _manager.notify(
                    websocket,
                    StatusMessage(
                        code="recipient_not_connected",
                        detail=f"Recipient '{message.recipient_id}' is not connected.",
                    ),
                )
    except WebSocketDisconnect:
        await _manager.disconnect(user_id, websocket)
