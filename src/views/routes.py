"""Router definitions for HTTP and websocket endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.controllers.message_controller import ConnectionManager, RecipientNotConnectedError
from src.models.message import InboundMessage, StatusMessage, TestMessageRequest

router = APIRouter()

_manager = ConnectionManager()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health probe for monitoring."""

    return {"status": "ok"}


@router.post("/test/messages", status_code=status.HTTP_202_ACCEPTED)
async def send_test_message(payload: TestMessageRequest) -> dict[str, str]:
    """HTTP endpoint to deliver a test message to a connected websocket client."""

    inbound = InboundMessage(recipient_id=payload.recipient_id, content=payload.content)
    try:
        await _manager.send_personal_message(sender_id=payload.sender_id, message=inbound)
    except RecipientNotConnectedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient '{payload.recipient_id}' is not connected.",
        ) from exc

    return {"status": "sent"}


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
