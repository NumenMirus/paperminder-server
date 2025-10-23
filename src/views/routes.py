"""Router definitions for HTTP and websocket endpoints."""

from __future__ import annotations

import json
from json import JSONDecodeError
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.controllers.message_controller import ConnectionManager, RecipientNotConnectedError
from src.services import PrinterService, MessageService
from src.models.message import (
    InboundMessage,
    PrinterRegistrationRequest,
    PrinterRegistrationResponse,
    StatusMessage,
    SubscriptionRequest,
    MessageRequest,
    PrinterResponse
)

router = APIRouter(prefix="/api")
ws_router = APIRouter()  # No prefix for backward compatibility

_manager = ConnectionManager()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health probe for monitoring."""

    return {"status": "ok"}


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

    return {"status": "sent"}


@router.post("/printer/register", status_code=status.HTTP_201_CREATED, response_model=PrinterRegistrationResponse)
async def register_printer_endpoint(payload: PrinterRegistrationRequest) -> PrinterRegistrationResponse:
    """HTTP endpoint to register a new printer in the system."""

    printer = PrinterService.register(
        name=payload.name,
        uuid=str(payload.uuid),
        location=payload.location,
        user_uuid=str(payload.user_uuid),
    )
    
    return PrinterRegistrationResponse(
        id=printer.id,
        name=printer.name,
        uuid=payload.uuid,
        location=printer.location,
        user_uuid=payload.user_uuid,
        created_at=printer.created_at,
    )


@router.get("/printers", status_code=status.HTTP_200_OK)
async def list_printers() -> list[PrinterResponse]:
    """HTTP endpoint to list all registered printers."""
    printers = await PrinterService.get_all()
    return [PrinterResponse(
        id=printer.id,
        name=printer.name,
        uuid=UUID(printer.uuid),
        location=printer.location
    ) for printer in printers]


@router.delete("/printer/{printer_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_printer_endpoint(printer_uuid: UUID) -> None:
    """HTTP endpoint to delete a registered printer by UUID."""
    success = PrinterService.delete(str(printer_uuid))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer with UUID '{printer_uuid}' not found.",
        )


@ws_router.websocket("/ws/{user_id}")
async def websocket_entrypoint(websocket: WebSocket, user_id: UUID) -> None:
    user_key = str(user_id)
    await _manager.connect(user_key, websocket)
    await _manager.notify(
        websocket,
        StatusMessage(code="info", detail="connected"),
    )
    
    # Send any cached messages the user may have missed while offline
    await _manager.send_cached_messages(user_key, websocket)

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
