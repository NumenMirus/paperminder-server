"""Pydantic models for firmware updates and rollout management."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(UTC)


# ============================================================================
# Firmware Management Models
# ============================================================================

class FirmwareUploadRequest(BaseModel):
    """Request model for uploading a new firmware version."""

    version: str = Field(..., min_length=1, max_length=16, description="Semantic version (e.g., 1.0.0)")
    platform: str = Field(..., min_length=1, max_length=32, description="Target platform (e.g., esp8266, esp32)")
    channel: Literal["stable", "beta", "canary"] = Field("stable", description="Update channel")
    release_notes: str | None = Field(None, description="Release notes for this version")
    changelog: str | None = Field(None, description="Detailed changelog")
    mandatory: bool = Field(False, description="Whether this update is mandatory")
    min_upgrade_version: str | None = Field(None, max_length=16, description="Minimum version that can upgrade to this")


class FirmwareVersionResponse(BaseModel):
    """Response model for firmware version details."""

    id: int
    version: str
    platform: str
    channel: str
    file_size: int
    md5_checksum: str
    sha256_checksum: str | None
    release_notes: str | None
    changelog: str | None
    mandatory: bool
    min_upgrade_version: str | None
    released_at: datetime
    deprecated_at: datetime | None
    download_count: int
    success_count: int
    failure_count: int


class FirmwareDownloadResponse(BaseModel):
    """Response model for firmware file download."""

    version: str
    file_data: bytes  # BLOB data
    md5_checksum: str
    file_size: int


# ============================================================================
# Printer Models with Firmware Info
# ============================================================================

class PrinterDetailsResponse(BaseModel):
    """Extended printer details including firmware status."""

    id: int
    name: str
    uuid: UUID
    location: str
    user_uuid: UUID
    created_at: datetime

    # Firmware tracking
    platform: str
    firmware_version: str
    auto_update: bool
    update_channel: str

    # Connection status
    online: bool
    last_connected: datetime | None
    last_ip: str | None


class PrinterListResponse(BaseModel):
    """Response model for listing printers."""

    printers: list[PrinterDetailsResponse]
    total: int


# ============================================================================
# Rollout Management Models
# ============================================================================

class RolloutTargetSpec(BaseModel):
    """Targeting criteria for a rollout."""

    all: bool = Field(False, description="Target all printers")
    user_ids: list[UUID] | None = Field(None, description="Specific user IDs to target")
    printer_ids: list[UUID] | None = Field(None, description="Specific printer IDs to target")
    channels: list[str] | None = Field(None, description="Update channels to target")
    min_version: str | None = Field(None, max_length=16, description="Minimum firmware version to target")
    max_version: str | None = Field(None, max_length=16, description="Maximum firmware version to target")


class RolloutCreateRequest(BaseModel):
    """Request model for creating a new rollout."""

    firmware_version: str = Field(..., min_length=1, max_length=16, description="Firmware version to deploy")
    target: RolloutTargetSpec = Field(..., description="Targeting criteria")
    rollout_type: Literal["immediate", "gradual", "scheduled"] = Field(
        "immediate", description="Type of rollout"
    )
    rollout_percentage: int = Field(
        100, ge=0, le=100, description="Percentage of targets for gradual rollout"
    )
    scheduled_for: datetime | None = Field(None, description="When to start scheduled rollout")

    @field_validator('rollout_percentage')
    @classmethod
    def validate_percentage(cls, v: int, info) -> int:
        if info.data.get('rollout_type') == 'gradual' and v == 0:
            raise ValueError('rollout_percentage must be > 0 for gradual rollouts')
        return v


class RolloutUpdateRequest(BaseModel):
    """Request model for updating an existing rollout."""

    status: Literal["active", "paused", "cancelled"] | None = Field(None, description="New rollout status")
    rollout_percentage: int | None = Field(None, ge=0, le=100, description="Updated rollout percentage")


class RolloutResponse(BaseModel):
    """Response model for rollout details."""

    id: int
    firmware_version: str
    channel: str
    status: str
    rollout_type: str
    rollout_percentage: int
    scheduled_for: datetime | None
    total_targets: int
    completed_count: int
    failed_count: int
    declined_count: int
    pending_count: int
    created_at: datetime
    updated_at: datetime


class RolloutListResponse(BaseModel):
    """Response model for listing rollouts."""

    rollouts: list[RolloutResponse]


class RolloutDetailResponse(RolloutResponse):
    """Extended rollout details with target information."""

    target_all: bool
    target_user_ids: list[str] | None
    target_printer_ids: list[str] | None
    target_channels: list[str] | None
    min_version: str | None
    max_version: str | None
    targets: list["RolloutTargetInfo"] | None = None


class RolloutTargetInfo(BaseModel):
    """Information about a rollout target."""

    printer_id: str
    status: str
    started_at: datetime | None
    completed_at: datetime | None


# ============================================================================
# Update History Models
# ============================================================================

class UpdateHistoryResponse(BaseModel):
    """Response model for update history entry."""

    id: int
    rollout_id: int | None
    printer_id: str
    firmware_version: str
    status: str
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    last_percent: int
    last_status_message: str | None


class UpdateHistoryListResponse(BaseModel):
    """Response model for listing update history."""

    updates: list[UpdateHistoryResponse]


# ============================================================================
# WebSocket Message Models
# ============================================================================

class FirmwareUpdateMessage(BaseModel):
    """Server -> Printer: Push firmware update."""

    kind: Literal["firmware_update"] = "firmware_update"
    version: str = Field(..., description="Target firmware version")
    platform: str = Field(..., description="Target platform")
    url: str = Field(..., description="HTTPS URL to download firmware")
    md5: str = Field(..., description="MD5 checksum for verification")


class FirmwareDeclinedMessage(BaseModel):
    """Printer -> Server: Printer declined update (auto_update disabled)."""

    kind: Literal["firmware_declined"] = "firmware_declined"
    version: str = Field(..., description="Declined firmware version")
    auto_update: bool = Field(..., description="Whether auto_update is enabled")


class FirmwareProgressMessage(BaseModel):
    """Printer -> Server: Firmware download/install progress."""

    kind: Literal["firmware_progress"] = "firmware_progress"
    percent: int = Field(..., ge=-1, le=100, description="Progress percentage (-1 for error)")
    status: str = Field(..., description="Human-readable status message")


class FirmwareCompleteMessage(BaseModel):
    """Printer -> Server: Firmware update completed successfully."""

    kind: Literal["firmware_complete"] = "firmware_complete"
    version: str = Field(..., description="Successfully installed firmware version")


class FirmwareFailedMessage(BaseModel):
    """Printer -> Server: Firmware update failed."""

    kind: Literal["firmware_failed"] = "firmware_failed"
    error: str = Field(..., description="Error message describing the failure")


# ============================================================================
# Extended Subscription Request
# ============================================================================

class ExtendedSubscriptionRequest(BaseModel):
    """Extended subscription request with firmware information."""

    printer_name: str = Field(..., min_length=1, description="Human readable printer identifier")
    api_key: str = Field(..., min_length=1, description="API key for authorization")
    platform: str = Field("esp8266", min_length=1, max_length=32, description="Printer hardware platform")
    firmware_version: str = Field("0.0.0", description="Current firmware version on printer")
    auto_update: bool = Field(True, description="Whether printer accepts automatic updates")
    update_channel: Literal["stable", "beta", "canary"] = Field(
        "stable", description="Printer's update channel preference"
    )
