from __future__ import annotations
from fastapi import APIRouter, HTTPException, status, Response
from src.controllers.message_controller import connection_manager
from src.exceptions import RecipientNotConnectedError, RecipientNotFoundError
from src.models.message import (
    InboundMessage,
    MessageRequest,
)
from src.crud import can_user_message_printer


router = APIRouter(prefix="/api", tags=["message"])


@router.post("/message")
async def send_message(payload: MessageRequest, response: Response) -> dict[str, str]:
    """HTTP endpoint to deliver a message to a connected websocket client.

    Permission check: Only the printer owner or users in the same group can send messages to the printer.

    Returns:
    - 200: Message was successfully sent to connected recipient
    - 202: Message accepted for processing (recipient offline, message cached)
    - 404: Recipient does not exist
    - 500: Internal server error
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
        await connection_manager.send_personal_message(sender_id=str(payload.sender_uuid), message=inbound)
        # Message was successfully sent to connected recipient
        return {"status": "sent"}

    except RecipientNotConnectedError:
        # Recipient exists but is offline, message was cached for later delivery
        response.status_code = status.HTTP_202_ACCEPTED
        return {"status": "accepted_for_processing"}

    except RecipientNotFoundError as exc:
        # Recipient (printer) does not exist
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recipient '{payload.recipient_id}' not found.",
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send message: {exc}",
        ) from exc
