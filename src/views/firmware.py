"""API endpoints for firmware update management."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import Response
from authx import RequestToken

from src.config import get_settings
from src.models.firmware import (
    FirmwareUploadRequest,
    FirmwareVersionResponse,
    FirmwareDownloadResponse,
    PrinterDetailsResponse,
    PrinterListResponse,
    RolloutCreateRequest,
    RolloutUpdateRequest,
    RolloutResponse,
    RolloutDetailResponse,
    RolloutTargetInfo,
    RolloutListResponse,
    UpdateHistoryListResponse,
    UpdateHistoryResponse,
)
from src.services.firmware_service import FirmwareService
from src.services.rollout_service import RolloutService
from src.crud import (
    get_printer,
    get_user_printers,
    get_printers_by_filters,
    get_printer_update_history,
    get_rollout,
    get_rollout_update_history,
    get_all_firmware_versions,
    get_firmware_version,
    get_firmware_version_by_id,
    compare_versions,
)
from src.database import FirmwareVersion, Printer, UpdateRollout

router = APIRouter(prefix="/api", tags=["firmware"])


# ============================================================================
# Firmware Management Endpoints (Admin Only)
# ============================================================================


@router.post(
    "/firmware/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=FirmwareVersionResponse,
)
async def upload_firmware(
    file: UploadFile = File(..., description="Firmware binary file"),
    version: str = File(..., description="Semantic version (e.g., 1.0.0)"),
    channel: str = File("stable", description="Update channel (stable, beta, canary)"),
    release_notes: str | None = File(None, description="Release notes"),
    changelog: str | None = File(None, description="Detailed changelog"),
    mandatory: bool = File(False, description="Whether this is a mandatory update"),
    min_upgrade_version: str | None = File(None, description="Minimum version that can upgrade")
) -> FirmwareVersionResponse:
    """Upload a new firmware version.

    Admin-only endpoint for uploading firmware binaries.
    """
    # Read file data
    file_data = await file.read()

    # Validate file size
    settings = get_settings()
    max_size = settings.max_firmware_size if hasattr(settings, 'max_firmware_size') else 5 * 1024 * 1024  # 5MB default
    if len(file_data) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Firmware file too large (max {max_size} bytes)",
        )

    try:
        firmware = FirmwareService.upload_firmware(
            version=version,
            channel=channel,
            file_data=file_data,
            release_notes=release_notes,
            changelog=changelog,
            mandatory=mandatory,
            min_upgrade_version=min_upgrade_version,
        )
        return _firmware_to_response(firmware)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        import traceback
        error_details = f"Failed to upload firmware: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR: {error_details}")  # Log to server console
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload firmware: {str(e)}",
        ) from e


@router.get("/firmware/latest", response_model=FirmwareVersionResponse)
async def get_latest_firmware(
    channel: str = "stable"
) -> FirmwareVersionResponse:
    """Get the latest firmware version for a channel."""
    firmware = FirmwareService.get_latest_firmware(channel)
    if not firmware:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No firmware found for channel: {channel}",
        )

    return _firmware_to_response(firmware)


@router.get("/firmware/{version}", response_model=FirmwareVersionResponse)
async def get_firmware_by_version(
    version: str
) -> FirmwareVersionResponse:
    """Get firmware details by version."""
    firmware = FirmwareService.get_firmware(version)
    if not firmware:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware version {version} not found",
        )

    return _firmware_to_response(firmware)


@router.get("/firmware/download/{version}")
async def download_firmware(
    version: str
) -> Response:
    """Download firmware binary by version."""
    firmware = FirmwareService.get_firmware(version)
    if not firmware:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Firmware version {version} not found",
        )

    # Record download for statistics
    FirmwareService.record_download(firmware.id)

    # Return firmware as binary response
    return Response(
        content=firmware.file_data,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="paperminder-{version}.bin"',
            "Content-MD5": firmware.md5_checksum,
        },
    )


@router.get("/firmware", response_model=list[FirmwareVersionResponse])
async def list_firmware(
    channel: str | None = None
) -> list[FirmwareVersionResponse]:
    """List all firmware versions, optionally filtered by channel."""
    firmware_list = FirmwareService.list_firmware(channel)
    return [_firmware_to_response(fw) for fw in firmware_list]


# ============================================================================
# Printer Management Endpoints
# ============================================================================


@router.get("/printers", response_model=PrinterListResponse)
async def list_printers(
    user_id: UUID | None = None,
    online: bool | None = None,
    firmware_version: str | None = None,
    channel: str | None = None
) -> PrinterListResponse:
    """List printers with optional filters."""
    user_uuid = str(user_id) if user_id else None

    # TODO: Re-enable authentication when ready
    # # If filtering by user, verify the requesting user owns those printers
    # if user_uuid:
    #     requesting_user_uuid = _user["uid"]
    #     if user_uuid != requesting_user_uuid:
    #         # User can only view their own printers
    #         printers = get_user_printers(requesting_user_uuid)
    #     else:
    #         printers = get_user_printers(user_uuid)
    # else:
    #     printers = get_printers_by_filters(
    #         user_uuid=user_uuid,
    #         online=online,
    #         firmware_version=firmware_version,
    #         channel=channel,
    #     )

    # Auth disabled for debugging - return all matching printers
    if user_uuid:
        printers = get_user_printers(user_uuid)
    else:
        printers = get_printers_by_filters(
            user_uuid=user_uuid,
            online=online,
            firmware_version=firmware_version,
            channel=channel,
        )

    return PrinterListResponse(
        printers=[_printer_to_response(p) for p in printers],
        total=len(printers),
    )


@router.get("/printers/{printer_id}", response_model=PrinterDetailsResponse)
async def get_printer_details(
    printer_id: UUID
) -> PrinterDetailsResponse:
    """Get detailed information about a printer."""
    printer = get_printer(uuid=str(printer_id))
    if not printer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Printer not found",
        )

    # TODO: Verify user owns this printer (auth disabled for debugging)
    # requesting_user_uuid = _user["uid"]
    # if printer.user_uuid != requesting_user_uuid:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="You do not have access to this printer",
    #     )

    return _printer_to_response(printer)


@router.get("/printers/{printer_id}/updates", response_model=UpdateHistoryListResponse)
async def get_printer_updates(
    printer_id: UUID,
    limit: int = 100
) -> UpdateHistoryListResponse:
    """Get update history for a printer."""
    printer = get_printer(uuid=str(printer_id))
    if not printer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Printer not found",
        )

    # TODO: Verify user owns this printer (auth disabled for debugging)
    # requesting_user_uuid = _user["uid"]
    # if printer.user_uuid != requesting_user_uuid:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="You do not have access to this printer",
    #     )

    history = get_printer_update_history(str(printer_id), limit)
    return UpdateHistoryListResponse(
        updates=[_update_history_to_response(h) for h in history]
    )


# ============================================================================
# Rollout Management Endpoints (Admin Only)
# ============================================================================


@router.post(
    "/rollouts",
    status_code=status.HTTP_201_CREATED,
    response_model=RolloutResponse,
)
async def create_rollout(
    payload: RolloutCreateRequest
) -> RolloutResponse:
    """Create a new firmware rollout campaign.

    Admin-only endpoint for managing firmware deployments.
    """
    try:
        rollout = await RolloutService.create_rollout(
            firmware_version=payload.firmware_version,
            target_all=payload.target.all,
            target_user_ids=[str(uid) for uid in payload.target.user_ids] if payload.target.user_ids else None,
            target_printer_ids=[str(pid) for pid in payload.target.printer_ids] if payload.target.printer_ids else None,
            target_channels=payload.target.channels,
            min_version=payload.target.min_version,
            max_version=payload.target.max_version,
            rollout_type=payload.rollout_type,
            rollout_percentage=payload.rollout_percentage,
            scheduled_for=payload.scheduled_for,
        )
        return _rollout_to_response(rollout)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        import traceback
        error_details = f"Failed to create rollout: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR: {error_details}")  # Log to server console
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create rollout: {str(e)}",
        ) from e


@router.get("/rollouts", response_model=RolloutListResponse)
async def list_rollouts(
    status: str | None = None
) -> RolloutListResponse:
    """List all rollouts, optionally filtered by status."""
    rollouts = RolloutService.list_rollouts(status)
    return RolloutListResponse(
        rollouts=[_rollout_to_response(r) for r in rollouts]
    )


@router.get("/rollouts/{rollout_id}", response_model=RolloutDetailResponse)
async def get_rollout_details(
    rollout_id: int
) -> RolloutDetailResponse:
    """Get detailed information about a rollout."""
    rollout = get_rollout(rollout_id)
    if not rollout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rollout not found",
        )

    response = _rollout_detail_to_response(rollout)

    # Get update history for this rollout
    history = get_rollout_update_history(rollout_id)
    targets = [
        RolloutTargetInfo(
            printer_id=h.printer_id,
            status=h.status,
            started_at=h.started_at,
            completed_at=h.completed_at,
        ) for h in history
    ]

    # Update response with targets using model_copy
    response = response.model_copy(update={"targets": targets})

    return response


@router.patch("/rollouts/{rollout_id}", response_model=RolloutResponse)
async def update_rollout(
    rollout_id: int,
    payload: RolloutUpdateRequest
) -> RolloutResponse:
    """Update a rollout (pause/resume/cancel/adjust percentage)."""
    rollout = get_rollout(rollout_id)
    if not rollout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rollout not found",
        )

    try:
        if payload.status:
            if payload.status == "paused":
                RolloutService.pause_rollout(rollout_id)
            elif payload.status == "active":
                RolloutService.resume_rollout(rollout_id)
            elif payload.status == "cancelled":
                RolloutService.cancel_rollout(rollout_id)

        if payload.rollout_percentage is not None:
            RolloutService.increase_rollout_percentage(rollout_id, payload.rollout_percentage)

        # Refresh rollout from database
        rollout = get_rollout(rollout_id)
        if not rollout:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Rollout not found after update",
            )
        return _rollout_to_response(rollout)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        import traceback
        error_details = f"Failed to update rollout: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR: {error_details}")  # Log to server console
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update rollout: {str(e)}",
        ) from e


@router.delete("/rollouts/{rollout_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rollout(
    rollout_id: int
) -> None:
    """Delete a rollout."""
    success = RolloutService.delete_rollout(rollout_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rollout not found",
        )


# ============================================================================
# Helper Functions
# ============================================================================


def _firmware_to_response(firmware: FirmwareVersion) -> FirmwareVersionResponse:
    """Convert database model to response model."""
    return FirmwareVersionResponse(
        id=firmware.id,
        version=firmware.version,
        channel=firmware.channel,
        file_size=firmware.file_size,
        md5_checksum=firmware.md5_checksum,
        sha256_checksum=firmware.sha256_checksum,
        release_notes=firmware.release_notes,
        changelog=firmware.changelog,
        mandatory=firmware.mandatory,
        min_upgrade_version=firmware.min_upgrade_version,
        released_at=firmware.released_at,
        deprecated_at=firmware.deprecated_at,
        download_count=firmware.download_count,
        success_count=firmware.success_count,
        failure_count=firmware.failure_count,
    )


def _printer_to_response(printer: Printer) -> PrinterDetailsResponse:
    """Convert database model to response model."""
    return PrinterDetailsResponse(
        id=printer.id,
        name=printer.name,
        uuid=UUID(printer.uuid),
        location=printer.location,
        user_uuid=UUID(printer.user_uuid),
        created_at=printer.created_at,
        firmware_version=printer.firmware_version,
        auto_update=printer.auto_update,
        update_channel=printer.update_channel,
        online=printer.online,
        last_connected=printer.last_connected,
        last_ip=printer.last_ip,
    )


def _rollout_to_response(rollout: UpdateRollout) -> RolloutResponse:
    """Convert database model to response model."""
    # Get firmware version
    firmware = get_firmware_version_by_id(rollout.firmware_version_id)

    return RolloutResponse(
        id=rollout.id,
        firmware_version=firmware.version if firmware else "unknown",
        channel=firmware.channel if firmware else "unknown",
        status=rollout.status,
        rollout_type=rollout.rollout_type,
        rollout_percentage=rollout.rollout_percentage,
        scheduled_for=rollout.scheduled_for,
        total_targets=rollout.total_targets,
        completed_count=rollout.completed_count,
        failed_count=rollout.failed_count,
        declined_count=rollout.declined_count,
        pending_count=rollout.pending_count,
        created_at=rollout.created_at,
        updated_at=rollout.updated_at,
    )


def _rollout_detail_to_response(rollout: UpdateRollout) -> RolloutDetailResponse:
    """Convert database model to detailed response model."""
    import json
    basic_response = _rollout_to_response(rollout)

    # Parse JSON fields
    target_user_ids = json.loads(rollout.target_user_ids) if rollout.target_user_ids else None
    target_printer_ids = json.loads(rollout.target_printer_ids) if rollout.target_printer_ids else None
    target_channels = json.loads(rollout.target_channels) if rollout.target_channels else None

    return RolloutDetailResponse(
        **basic_response.model_dump(),
        target_all=rollout.target_all,
        target_user_ids=target_user_ids,
        target_printer_ids=target_printer_ids,
        target_channels=target_channels,
        min_version=rollout.min_version,
        max_version=rollout.max_version,
        targets=None,  # Populated separately
    )


def _update_history_to_response(history) -> UpdateHistoryResponse:
    """Convert update history to response model."""
    return UpdateHistoryResponse(
        id=history.id,
        rollout_id=history.rollout_id,
        printer_id=history.printer_id,
        firmware_version=history.firmware_version,
        status=history.status,
        error_message=history.error_message,
        started_at=history.started_at,
        completed_at=history.completed_at,
        last_percent=history.last_percent,
        last_status_message=history.last_status_message,
    )


def _update_history_to_target_info(history) -> dict:
    """Convert update history to target info dict."""
    return {
        "printer_id": history.printer_id,
        "status": history.status,
        "started_at": history.started_at,
        "completed_at": history.completed_at,
    }
