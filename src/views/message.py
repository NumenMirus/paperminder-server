from __future__ import annotations
from fastapi import APIRouter, HTTPException, status
from src.controllers.message_controller import connection_manager, RecipientNotConnectedError
from src.models.message import (
    InboundMessage,
    MessageRequest,
)
from src.crud import can_user_message_printer


router = APIRouter(prefix="/api", tags=["message"])


@router.post("/message", status_code=status.HTTP_202_ACCEPTED)
async def send_message(payload: MessageRequest) -> dict[str, str]:
    """HTTP endpoint to deliver a message to a connected websocket client.
    
    Permission check: Only the printer owner or users in the same group can send messages to the printer.
    """

    # Check if the sender has permission to send messages to this printer
    # if not can_user_message_printer(str(payload.sender_uuid), str(payload.recipient_id)):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="You do not have permission to send messages to this printer. "
    #                "Only the printer owner or users in the same group can send messages.",
    #     )

    inbound = InboundMessage(
        recipient_id=payload.recipient_id,
        sender_name=payload.sender_name,
        message=payload.message,
    )

    try:
        await connection_manager.send_personal_message(sender_id=payload.sender_name, message=inbound)

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
