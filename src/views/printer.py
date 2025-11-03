"""Printer management routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.services import PrinterService
from src.models.message import (
    PrinterRegistrationRequest,
    PrinterRegistrationResponse,
    PrinterResponse
)

router = APIRouter(prefix="/api/printer", tags=["printer"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=PrinterRegistrationResponse)
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


@router.get("/list", status_code=status.HTTP_200_OK, tags=["printer"])
async def list_printers() -> list[PrinterResponse]:
    """HTTP endpoint to list all registered printers."""
    printers = await PrinterService.get_all()
    return [PrinterResponse(
        id=printer.id,
        name=printer.name,
        uuid=UUID(printer.uuid),
        location=printer.location
    ) for printer in printers]


@router.delete("/{printer_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_printer_endpoint(printer_uuid: UUID) -> None:
    """HTTP endpoint to delete a registered printer by UUID."""
    success = PrinterService.delete(str(printer_uuid))
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer with UUID '{printer_uuid}' not found.",
        )
