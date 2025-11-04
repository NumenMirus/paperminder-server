from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from src.services import PrinterService
from src.models.message import (
    PrinterRegistrationRequest,
    PrinterRegistrationResponse,
    PrinterResponse,
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


@router.post("/{printer_uuid}/groups/{group_uuid}", status_code=status.HTTP_201_CREATED)
async def add_printer_to_group_endpoint(printer_uuid: UUID, group_uuid: UUID) -> dict:
    """HTTP endpoint to add a printer to a group.
    
    A printer can belong to multiple groups. This endpoint adds the printer
    to the specified group.
    """
    success = PrinterService.add_to_group(
        printer_uuid=str(printer_uuid),
        group_uuid=str(group_uuid),
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer or group not found, or printer already in group.",
        )
    
    return {
        "message": f"Printer {printer_uuid} added to group {group_uuid}",
        "printer_uuid": str(printer_uuid),
        "group_uuid": str(group_uuid),
    }


@router.delete("/{printer_uuid}/groups/{group_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_printer_from_group_endpoint(printer_uuid: UUID, group_uuid: UUID) -> None:
    """HTTP endpoint to remove a printer from a group."""
    success = PrinterService.remove_from_group(
        printer_uuid=str(printer_uuid),
        group_uuid=str(group_uuid),
    )
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Printer not found in the specified group.",
        )


@router.get("/{printer_uuid}/groups", status_code=status.HTTP_200_OK)
async def get_printer_groups_endpoint(printer_uuid: UUID) -> dict:
    """HTTP endpoint to get all groups that a printer belongs to."""
    groups = PrinterService.get_printer_groups(str(printer_uuid))
    
    return {
        "printer_uuid": str(printer_uuid),
        "groups": [
            {
                "uuid": group.uuid,
                "name": group.name,
                "owner_uuid": group.owner_uuid,
                "colour": group.colour,
            }
            for group in groups
        ],
    }
