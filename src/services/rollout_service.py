"""Service layer for firmware rollout management."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from src.database import UpdateRollout, Printer
from src.crud import (
    create_rollout,
    get_rollout,
    get_all_rollouts,
    get_rollouts_by_status,
    update_rollout_status,
    update_rollout_percentage,
    update_rollout_progress,
    delete_rollout,
    get_printers_by_filters,
    get_printer,
    create_update_record,
    compare_versions,
)
from src.services.firmware_service import FirmwareService


class RolloutService:
    """Service for managing firmware update rollouts."""

    @staticmethod
    async def create_rollout(
        firmware_version: str,
        target_all: bool = False,
        target_user_ids: list[str] | None = None,
        target_printer_ids: list[str] | None = None,
        target_channels: list[str] | None = None,
        min_version: str | None = None,
        max_version: str | None = None,
        rollout_type: str = "immediate",
        rollout_percentage: int = 100,
        scheduled_for: datetime | None = None,
    ) -> UpdateRollout:
        """Create a new firmware rollout (platform-agnostic).

        Args:
            firmware_version: Target firmware version string (e.g., "1.2.0")
            target_all: Whether to target all printers
            target_user_ids: Optional list of user IDs to target
            target_printer_ids: Optional list of printer IDs to target
            target_channels: Optional list of channels to target
            min_version: Optional minimum firmware version
            max_version: Optional maximum firmware version
            rollout_type: Type of rollout (immediate, gradual, scheduled)
            rollout_percentage: Percentage for gradual rollout
            scheduled_for: Optional scheduled start time

        Returns:
            The created UpdateRollout object

        Raises:
            ValueError: If validation fails

        Note:
            Rollouts are platform-agnostic. Each printer will receive firmware
            for its own platform when the update is delivered.
        """
        # Validate rollout type
        if rollout_type not in ["immediate", "gradual", "scheduled"]:
            raise ValueError(f"Invalid rollout type: {rollout_type}")

        # Validate percentage for gradual rollouts
        if rollout_type == "gradual" and (rollout_percentage < 1 or rollout_percentage > 100):
            raise ValueError("Rollout percentage must be between 1 and 100 for gradual rollouts")

        # Validate scheduled time for scheduled rollouts
        if rollout_type == "scheduled" and not scheduled_for:
            raise ValueError("Scheduled time required for scheduled rollouts")

        # Create rollout (firmware_version is stored as string, platform-agnostic)
        rollout = create_rollout(
            firmware_version=firmware_version,
            target_all=target_all,
            target_user_ids=target_user_ids,
            target_printer_ids=target_printer_ids,
            target_channels=target_channels,
            min_version=min_version,
            max_version=max_version,
            rollout_type=rollout_type,
            rollout_percentage=rollout_percentage,
            scheduled_for=scheduled_for,
        )

        # Calculate and set target printers, and get the list
        target_printers = RolloutService._calculate_rollout_targets(rollout)

        # Notify connected printers immediately
        await RolloutService._notify_connected_printers(rollout, target_printers)

        return rollout

    @staticmethod
    def _calculate_rollout_targets(rollout: UpdateRollout) -> list[Printer]:
        """Calculate target printers for a rollout and update counters.

        Args:
            rollout: The rollout to calculate targets for

        Returns:
            List of unique target printers
        """

        if rollout.target_channels:
            # For channel-based targeting, we need to get printers matching those channels
            # This is handled by iterating through channels
            target_printers = []
            for channel in rollout.target_channels:
                channel_printers = get_printers_by_filters(channel=channel)
                target_printers.extend(channel_printers)

            # Apply version filters
            if rollout.min_version or rollout.max_version:
                filtered_printers = []
                for printer in target_printers:
                    if rollout.min_version and compare_versions(printer.firmware_version, rollout.min_version) < 0:
                        continue
                    if rollout.max_version and compare_versions(printer.firmware_version, rollout.max_version) > 0:
                        continue
                    filtered_printers.append(printer)
                target_printers = filtered_printers
        elif rollout.target_all:
            target_printers = get_printers_by_filters()
        elif rollout.target_user_ids:
            # Target specific users
            target_printers = []
            for user_uuid in rollout.target_user_ids:
                user_printers = get_printers_by_filters(user_uuid=user_uuid)
                target_printers.extend(user_printers)
        elif rollout.target_printer_ids:
            # Target specific printers
            target_printers = []
            for printer_uuid in rollout.target_printer_ids:
                printer = get_printer(printer_uuid)
                if printer:
                    target_printers.append(printer)
        else:
            target_printers = []

        # Get unique printers
        unique_printers = list({p.uuid: p for p in target_printers}.values())

        # Update rollout counters
        from src.database import session_scope
        with session_scope() as session:
            rollout_update = session.query(UpdateRollout).filter_by(id=rollout.id).first()
            if rollout_update:
                rollout_update.total_targets = len(unique_printers)
                rollout_update.pending_count = len(unique_printers)
                session.flush()

        return unique_printers

    @staticmethod
    async def _notify_connected_printers(rollout: UpdateRollout, target_printers: list[Printer]) -> None:
        """Push firmware updates to currently connected printers.

        Each printer receives firmware for their own platform.

        Args:
            rollout: The rollout object (platform-agnostic)
            target_printers: List of target Printer objects
        """
        # Import here to avoid circular dependency
        from src.controllers.message_controller import connection_manager
        from src.config import get_settings

        # Get base URL for firmware downloads
        settings = get_settings()
        base_url = getattr(settings, 'base_url', 'http://localhost:8000')

        logger = logging.getLogger(__name__)
        notified_count = 0
        not_connected_count = 0
        skipped_no_firmware = 0

        # Track printers that were actually notified (to decrement pending_count)
        notified_printers = []

        # Notify connected printers
        for printer in target_printers:
            # Check if printer is connected and has auto_update enabled
            if connection_manager.is_printer_connected(printer.uuid):
                if printer.auto_update:
                    # Check rollout timing
                    if RolloutService._should_update_now(rollout, printer):
                        # Get firmware for this printer's platform
                        firmware = FirmwareService.get_firmware(rollout.firmware_version, printer.platform)

                        if not firmware:
                            logger.warning(f"No firmware found for platform {printer.platform} version {rollout.firmware_version}")
                            skipped_no_firmware += 1
                            continue

                        # Create platform-specific firmware update message
                        update_message = {
                            "kind": "firmware_update",
                            "version": firmware.version,
                            "platform": firmware.platform,
                            "url": f"{base_url}/api/firmware/download/{firmware.platform}/{firmware.version}",
                            "md5": firmware.md5_checksum
                        }

                        # Send firmware update
                        sent = await connection_manager.send_firmware_update(printer.uuid, update_message)
                        if sent:
                            # Record update start
                            await asyncio.to_thread(
                                create_update_record,
                                printer_id=printer.uuid,
                                firmware_version=firmware.version,
                                rollout_id=rollout.id,
                            )
                            notified_printers.append(printer.uuid)
                            notified_count += 1
                            logger.info(f"Rollout {rollout.id}: Pushed firmware {firmware.version} to connected printer {printer.uuid}")
                        else:
                            logger.warning(f"Rollout {rollout.id}: Failed to send update to printer {printer.uuid}")
                    else:
                        not_connected_count += 1
                        logger.debug(f"Rollout {rollout.id}: Printer {printer.uuid} connected but not eligible for update yet (timing/percentage)")
                else:
                    not_connected_count += 1
                    logger.debug(f"Rollout {rollout.id}: Printer {printer.uuid} connected but auto_update disabled")
            else:
                not_connected_count += 1
                logger.debug(f"Rollout {rollout.id}: Printer {printer.uuid} not connected")

        # Update rollout counters - decrement pending_count for notified printers
        if notified_printers:
            await asyncio.to_thread(
                update_rollout_progress,
                rollout_id=rollout.id,
                pending_decrement=len(notified_printers),
            )

        logger.info(
            f"Rollout {rollout.id}: Notified {notified_count} connected printers, "
            f"{not_connected_count} offline/disconnected, "
            f"{skipped_no_firmware} skipped (no firmware for their platform)"
        )

    @staticmethod
    def _should_update_now(rollout: UpdateRollout, printer: Printer) -> bool:
        """Check if a printer should receive the update now based on rollout configuration.

        Args:
            rollout: The rollout object
            printer: The printer object

        Returns:
            True if printer should update now, False otherwise
        """
        import hashlib

        # For scheduled rollouts, check if time has arrived
        if rollout.rollout_type == "scheduled":
            if not rollout.scheduled_for:
                return False
            if rollout.scheduled_for > datetime.now(UTC):
                return False

        # For gradual rollouts, check if printer is in the current percentage bucket
        if rollout.rollout_type == "gradual":
            # Calculate MD5 hash of printer UUID
            printer_hash = int(hashlib.md5(printer.uuid.encode()).hexdigest(), 16)
            bucket = printer_hash % 100
            if bucket >= rollout.rollout_percentage:
                return False

        return True

    @staticmethod
    def get_rollout(rollout_id: int) -> UpdateRollout | None:
        """Get rollout by ID.

        Args:
            rollout_id: The rollout database ID

        Returns:
            The UpdateRollout object or None if not found
        """
        return get_rollout(rollout_id)

    @staticmethod
    def list_rollouts(status: str | None = None) -> list[UpdateRollout]:
        """List rollouts, optionally filtered by status.

        Args:
            status: Optional status to filter by

        Returns:
            List of UpdateRollout objects
        """
        if status:
            return get_rollouts_by_status(status)
        return get_all_rollouts()

    @staticmethod
    def activate_rollout(rollout_id: int) -> bool:
        """Activate a pending rollout.

        Args:
            rollout_id: The rollout database ID

        Returns:
            True if activated, False if not found
        """
        return update_rollout_status(rollout_id, "active")

    @staticmethod
    def pause_rollout(rollout_id: int) -> bool:
        """Pause an active rollout.

        Args:
            rollout_id: The rollout database ID

        Returns:
            True if paused, False if not found
        """
        return update_rollout_status(rollout_id, "paused")

    @staticmethod
    def resume_rollout(rollout_id: int) -> bool:
        """Resume a paused rollout.

        Args:
            rollout_id: The rollout database ID

        Returns:
            True if resumed, False if not found
        """
        return update_rollout_status(rollout_id, "active")

    @staticmethod
    def cancel_rollout(rollout_id: int) -> bool:
        """Cancel a rollout.

        Args:
            rollout_id: The rollout database ID

        Returns:
            True if cancelled, False if not found
        """
        return update_rollout_status(rollout_id, "cancelled")

    @staticmethod
    def increase_rollout_percentage(rollout_id: int, new_percentage: int) -> bool:
        """Increase rollout percentage for gradual rollouts.

        Args:
            rollout_id: The rollout database ID
            new_percentage: New rollout percentage (0-100)

        Returns:
            True if updated, False if not found
        """
        if new_percentage < 0 or new_percentage > 100:
            raise ValueError("Rollout percentage must be between 0 and 100")

        return update_rollout_percentage(rollout_id, new_percentage)

    @staticmethod
    def delete_rollout(rollout_id: int) -> bool:
        """Delete a rollout.

        Args:
            rollout_id: The rollout database ID

        Returns:
            True if deleted, False if not found
        """
        return delete_rollout(rollout_id)

    @staticmethod
    def update_rollout_progress(
        rollout_id: int,
        completed_increment: int = 0,
        failed_increment: int = 0,
        declined_increment: int = 0,
    ) -> bool:
        """Update rollout progress counters.

        Args:
            rollout_id: The rollout database ID
            completed_increment: Increment completed count
            failed_increment: Increment failed count
            declined_increment: Increment declined count

        Returns:
            True if updated, False if not found
        """
        return update_rollout_progress(
            rollout_id=rollout_id,
            completed_increment=completed_increment,
            failed_increment=failed_increment,
            declined_increment=declined_increment,
            pending_decrement=completed_increment + failed_increment + declined_increment,
        )
