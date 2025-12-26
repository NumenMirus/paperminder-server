"""Service layer for firmware update orchestration."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from src.database import Printer, FirmwareVersion, UpdateRollout
from src.crud import (
    get_printer,
    update_printer_firmware_info,
    update_printer_connection_status,
    get_active_rollout_for_printer,
    create_update_record,
    update_update_progress,
    mark_update_complete,
    mark_update_failed,
    mark_update_declined,
    compare_versions,
)
from src.services.firmware_service import FirmwareService


class UpdateService:
    """Service for orchestrating firmware updates to printers."""

    @staticmethod
    def check_for_updates(printer_uuid: str) -> FirmwareVersion | None:
        """Check if a firmware update is available for a printer.

        Args:
            printer_uuid: The printer UUID

        Returns:
            FirmwareVersion if update available, None otherwise

        Note:
            This checks for rollouts targeting the printer, then fetches the
            appropriate firmware for the printer's platform.
        """
        printer = get_printer(printer_uuid)
        if not printer:
            return None

        # Check if auto-update is enabled
        if not printer.auto_update:
            return None

        # Get latest firmware for printer's channel and platform
        latest = FirmwareService.get_latest_firmware(printer.update_channel, printer.platform)
        if not latest:
            return None

        # Check if update is needed
        if compare_versions(latest.version, printer.firmware_version) > 0:
            # Check if there's an active rollout for this printer and version
            rollout = get_active_rollout_for_printer(printer_uuid, latest.version)

            if rollout and UpdateService.should_update_now(rollout, printer):
                # Rollout exists - get firmware for this specific printer's platform
                platform_firmware = FirmwareService.get_firmware(latest.version, printer.platform)
                if platform_firmware:
                    return platform_firmware
                # If no firmware exists for this printer's platform, skip update
                return None

        return None

    @staticmethod
    def should_update_now(rollout: UpdateRollout, printer: Printer) -> bool:
        """Determine if printer should receive update now (for gradual rollouts).

        Args:
            rollout: The rollout configuration
            printer: The printer to check

        Returns:
            True if printer should update now, False otherwise
        """
        if rollout.rollout_type == "immediate":
            return True

        if rollout.rollout_type == "gradual":
            # Use consistent hashing to assign printers to rollout buckets
            bucket = UpdateService._consistent_hash(printer.uuid) % 100
            return bucket < rollout.rollout_percentage

        if rollout.rollout_type == "scheduled":
            return datetime.now(UTC) >= (rollout.scheduled_for or datetime.now(UTC))

        return False

    @staticmethod
    def _consistent_hash(input_string: str) -> int:
        """Generate a consistent hash value for a string.

        Args:
            input_string: String to hash

        Returns:
            Integer hash value (0-2^31-1)
        """
        # Use MD5 for fast, consistent hashing
        hash_obj = hashlib.md5(input_string.encode())
        hash_bytes = hash_obj.digest()
        # Convert first 4 bytes to integer
        hash_int = int.from_bytes(hash_bytes[:4], byteorder="big")
        return hash_int

    @staticmethod
    def create_firmware_update_message(
        firmware: FirmwareVersion,
        base_url: str,
    ) -> dict:
        """Create a firmware update WebSocket message.

        Args:
            firmware: The firmware version to deploy
            base_url: Base URL for the API

        Returns:
            Dictionary containing the firmware update message
        """
        download_url = FirmwareService.generate_download_url(firmware.version, firmware.platform, base_url)

        return {
            "kind": "firmware_update",
            "version": firmware.version,
            "platform": firmware.platform,
            "url": download_url,
            "md5": firmware.md5_checksum,
        }

    @staticmethod
    def record_update_start(
        printer_uuid: str,
        firmware_version: str,
        rollout_id: int | None = None,
    ) -> bool:
        """Record the start of a firmware update.

        Args:
            printer_uuid: The printer UUID
            firmware_version: Target firmware version
            rollout_id: Optional rollout database ID

        Returns:
            True if recorded, False otherwise
        """
        try:
            create_update_record(
                printer_id=printer_uuid,
                firmware_version=firmware_version,
                rollout_id=rollout_id,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def handle_firmware_progress(
        printer_uuid: str,
        percent: int,
        status_message: str,
    ) -> bool:
        """Handle firmware update progress from printer.

        Args:
            printer_uuid: The printer UUID
            percent: Progress percentage (0-100, or -1 for error)
            status_message: Human-readable status message

        Returns:
            True if handled, False otherwise
        """
        return update_update_progress(
            printer_id=printer_uuid,
            percent=percent,
            status_message=status_message,
        )

    @staticmethod
    def handle_firmware_complete(
        printer_uuid: str,
        version: str,
    ) -> bool:
        """Handle successful firmware update completion.

        Args:
            printer_uuid: The printer UUID
            version: The firmware version that was installed

        Returns:
            True if handled, False otherwise
        """
        # Update printer's firmware version
        success = update_printer_firmware_info(
            uuid=printer_uuid,
            firmware_version=version,
        )

        # Mark update as complete
        if success:
            mark_update_complete(printer_uuid, version)

            # Update firmware statistics
            firmware = FirmwareService.get_firmware(version)
            if firmware:
                FirmwareService.record_success(firmware.id)

        return success

    @staticmethod
    def handle_firmware_failed(
        printer_uuid: str,
        error_message: str,
    ) -> bool:
        """Handle firmware update failure.

        Args:
            printer_uuid: The printer UUID
            error_message: Error message describing the failure

        Returns:
            True if handled, False otherwise
        """
        # Mark update as failed
        success = mark_update_failed(
            printer_id=printer_uuid,
            error_message=error_message,
        )

        # Get the latest pending update to record failure statistics
        # Note: This would require additional tracking to get the firmware_id
        # For now, we'll skip the statistics update

        return success

    @staticmethod
    def handle_firmware_declined(
        printer_uuid: str,
        version: str,
    ) -> bool:
        """Handle firmware update declined by printer.

        Args:
            printer_uuid: The printer UUID
            version: The firmware version that was declined

        Returns:
            True if handled, False otherwise
        """
        # Mark update as declined
        return mark_update_declined(
            printer_id=printer_uuid,
            version=version,
        )

    @staticmethod
    def update_printer_subscription_info(
        printer_uuid: str,
        firmware_version: str | None = None,
        platform: str | None = None,
        auto_update: bool | None = None,
        update_channel: str | None = None,
        online: bool = True,
        last_ip: str | None = None,
    ) -> bool:
        """Update printer firmware information from subscription message.

        Args:
            printer_uuid: The printer UUID
            firmware_version: Optional firmware version
            platform: Optional platform
            auto_update: Optional auto-update setting
            update_channel: Optional update channel
            online: Whether printer is online
            last_ip: Optional last IP address

        Returns:
            True if updated, False if printer not found
        """
        # Update firmware info
        success = update_printer_firmware_info(
            uuid=printer_uuid,
            firmware_version=firmware_version,
            platform=platform,
            auto_update=auto_update,
            update_channel=update_channel,
        )

        if success:
            # Update connection status
            update_printer_connection_status(
                uuid=printer_uuid,
                online=online,
                last_ip=last_ip,
            )

        return success
