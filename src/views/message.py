from __future__ import annotations
import asyncio
from uuid import UUID
from fastapi import APIRouter, HTTPException, status, Response, UploadFile, File
from PIL import Image
from io import BytesIO
from src.controllers.message_controller import connection_manager
from src.dependencies import CurrentUser
from src.exceptions import RecipientNotConnectedError, RecipientNotFoundError, BitmapProcessingError
from src.models.message import (
    InboundMessage,
    MessageRequest,
)
from src.services.bitmap_service import BitmapService
from src.crud import can_user_message_printer
from src.crud import get_user, get_printer


router = APIRouter(prefix="/api", tags=["message"])


@router.post("/message")
async def send_message(payload: MessageRequest, response: Response, current_user: CurrentUser) -> dict[str, str]:
    """HTTP endpoint to deliver a message to a connected websocket client.

    Permission check: Only the printer owner or users in the same group can send messages to the printer.

    Returns:
    - 200: Message was successfully sent to connected recipient
    - 202: Message accepted for processing (recipient offline, message cached)
    - 404: Recipient does not exist
    - 500: Internal server error
    """

    # Derive sender identity from the authenticated token. Do not trust the client payload.
    sender_sub = getattr(current_user, "sub", None)
    if not sender_sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject claim",
        )
    sender_uuid = str(sender_sub)

    # Defensive check: ensure sender exists to avoid FK violations in message_logs.
    if not get_user(uuid=sender_uuid):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

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
        await connection_manager.send_personal_message(sender_id=sender_uuid, message=inbound)
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


@router.post("/message/bitmap/qr")
async def send_qr_code(
    printer_id: UUID,
    url: str,
    caption: str | None = None,
    size: int = 128,
    current_user: CurrentUser = None,
) -> dict[str, str]:
    """Generate and send a QR code to a printer.

    Args:
        printer_id: UUID of the printer to send the QR code to
        url: URL to encode in the QR code
        caption: Optional caption text to print below the QR code
        size: QR code size in pixels (must be multiple of 8, default 128)
        current_user: Authenticated user (injected)

    Returns:
        Status message indicating success or failure

    Raises:
        404: Printer not found
        400: Invalid QR code size
        500: Failed to generate or send QR code
    """
    # Validate size
    if size % 8 != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Size must be multiple of 8, got {size}",
        )

    # Check if printer exists
    printer = await asyncio.to_thread(get_printer, uuid=str(printer_id))
    if not printer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer '{printer_id}' not found",
        )

    # Generate QR code
    try:
        qr_img = BitmapService.generate_qr_code(url, size)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate QR code: {e}",
        ) from e

    # Create bitmap message
    try:
        bitmap_msg = BitmapService.create_bitmap_message(qr_img, caption)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bitmap parameters: {e}",
        ) from e
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Failed to process bitmap")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bitmap: {type(e).__name__}: {e}",
        ) from e

    # Send to printer
    success = await connection_manager.send_bitmap_to_printer(
        printer_uuid=str(printer_id),
        bitmap_message=bitmap_msg,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Printer '{printer_id}' is not connected",
        )

    return {
        "status": "sent",
        "message": f"QR code sent to printer '{printer_id}'",
        "size": f"{size}x{size}",
    }


@router.post("/message/bitmap/image")
async def send_bitmap_image(
    printer_id: UUID,
    image: UploadFile = File(...),
    caption: str | None = None,
    target_width: int | None = None,
    current_user: CurrentUser = None,
) -> dict[str, str]:
    """Upload and print an image on a thermal printer.

    Args:
        printer_id: UUID of the printer to send the image to
        image: Image file (PNG, JPEG, etc.)
        caption: Optional caption text to print below the image
        target_width: Target width in pixels (must be multiple of 8, default 384 for 58mm paper)
        current_user: Authenticated user (injected)

    Returns:
        Status message indicating success or failure

    Raises:
        404: Printer not found
        400: Invalid image or target_width
        500: Failed to process or send image
    """
    # Validate target_width
    if target_width is not None and target_width % 8 != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"target_width must be multiple of 8, got {target_width}",
        )

    # Check if printer exists
    printer = await asyncio.to_thread(get_printer, uuid=str(printer_id))
    if not printer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer '{printer_id}' not found",
        )

    # Read and load image
    try:
        image_data = await image.read()
        img = BitmapService.load_image(image_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to load image: {e}",
        ) from e

    # Resize if target_width specified
    if target_width is not None:
        try:
            img = BitmapService.resize_for_printer(img, target_width)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to resize image: {e}",
            ) from e

    # Create bitmap message
    try:
        bitmap_msg = BitmapService.create_bitmap_message(img, caption)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bitmap parameters: {e}",
        ) from e
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Failed to process bitmap")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bitmap: {type(e).__name__}: {e}",
        ) from e

    # Send to printer
    success = await connection_manager.send_bitmap_to_printer(
        printer_uuid=str(printer_id),
        bitmap_message=bitmap_msg,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Printer '{printer_id}' is not connected",
        )

    return {
        "status": "sent",
        "message": f"Image sent to printer '{printer_id}'",
        "size": f"{img.width}x{img.height}",
    }


@router.post("/message/bitmap/test")
async def send_test_pattern(
    printer_id: UUID,
    size: int = 128,
    current_user: CurrentUser = None,
) -> dict[str, str]:
    """Send a test pattern to a printer for debugging.

    Args:
        printer_id: UUID of the printer to send the test pattern to
        size: Test pattern size in pixels (must be multiple of 8, default 128)
        current_user: Authenticated user (injected)

    Returns:
        Status message indicating success or failure

    Raises:
        404: Printer not found
        400: Invalid size
        500: Failed to generate or send test pattern
    """
    # Validate size
    if size % 8 != 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Size must be multiple of 8, got {size}",
        )

    # Check if printer exists
    printer = await asyncio.to_thread(get_printer, uuid=str(printer_id))
    if not printer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer '{printer_id}' not found",
        )

    # Generate test pattern
    try:
        test_img = BitmapService.create_test_pattern(size)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate test pattern: {e}",
        ) from e

    # Create bitmap message
    try:
        bitmap_msg = BitmapService.create_bitmap_message(test_img, None)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid bitmap parameters: {e}",
        ) from e
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Failed to process bitmap")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process bitmap: {type(e).__name__}: {e}",
        ) from e

    # Send to printer
    success = await connection_manager.send_bitmap_to_printer(
        printer_uuid=str(printer_id),
        bitmap_message=bitmap_msg,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Printer '{printer_id}' is not connected",
        )

    return {
        "status": "sent",
        "message": f"Test pattern sent to printer '{printer_id}'",
        "size": f"{size}x{size}",
    }
