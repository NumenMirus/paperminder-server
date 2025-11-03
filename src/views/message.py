from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from src.controllers.message_controller import ConnectionManager, RecipientNotConnectedError
from src.models.message import (
    InboundMessage,
    MessageRequest,
)


router = APIRouter(prefix="/api", tags=["message"])

_manager = ConnectionManager()


@router.post("/message", status_code=status.HTTP_202_ACCEPTED)
async def send_test_message(payload: MessageRequest) -> dict[str, str]:
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
        )
    
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {exc}",
        )

    return {"status": "sent"}
