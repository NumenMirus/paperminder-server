"""Service layer for firmware rollout management."""

from __future__ import annotations

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
    def create_rollout(
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
        """Create a new firmware rollout.

        Args:
            firmware_version: Target firmware version
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
            ValueError: If firmware version not found or validation fails
        """
        # Get firmware version
        firmware = FirmwareService.get_firmware(firmware_version)
        if not firmware:
            raise ValueError(f"Firmware version {firmware_version} not found")

        # Validate rollout type
        if rollout_type not in ["immediate", "gradual", "scheduled"]:
            raise ValueError(f"Invalid rollout type: {rollout_type}")

        # Validate percentage for gradual rollouts
        if rollout_type == "gradual" and (rollout_percentage < 1 or rollout_percentage > 100):
            raise ValueError("Rollout percentage must be between 1 and 100 for gradual rollouts")

        # Validate scheduled time for scheduled rollouts
        if rollout_type == "scheduled" and not scheduled_for:
            raise ValueError("Scheduled time required for scheduled rollouts")

        # Create rollout
        rollout = create_rollout(
            firmware_version_id=firmware.id,
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

        # Calculate and set target printers
        RolloutService._calculate_rollout_targets(rollout)

        return rollout

    @staticmethod
    def _calculate_rollout_targets(rollout: UpdateRollout) -> None:
        """Calculate target printers for a rollout and update counters.

        Args:
            rollout: The rollout to calculate targets for
        """
        import json
        # Parse JSON fields
        target_user_ids = json.loads(rollout.target_user_ids) if rollout.target_user_ids else None
        target_printer_ids = json.loads(rollout.target_printer_ids) if rollout.target_printer_ids else None
        target_channels = json.loads(rollout.target_channels) if rollout.target_channels else None

        # Build filter criteria
        filters = {}

        if target_channels:
            # For channel-based targeting, we need to get printers matching those channels
            # This is handled by iterating through channels
            target_printers = []
            for channel in target_channels:
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
        elif target_user_ids:
            # Target specific users
            target_printers = []
            for user_uuid in target_user_ids:
                user_printers = get_printers_by_filters(user_uuid=user_uuid)
                target_printers.extend(user_printers)
        elif target_printer_ids:
            # Target specific printers
            target_printers = []
            for printer_uuid in target_printer_ids:
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
            rollout = session.query(UpdateRollout).filter_by(id=rollout.id).first()
            if rollout:
                rollout.total_targets = len(unique_printers)
                rollout.pending_count = len(unique_printers)
                session.flush()

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
