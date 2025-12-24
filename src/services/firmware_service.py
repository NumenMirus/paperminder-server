"""Service layer for firmware file management."""

from __future__ import annotations

import hashlib
from typing import BinaryIO

from src.database import FirmwareVersion
from src.crud import (
    create_firmware_version,
    get_firmware_version,
    get_firmware_version_by_id,
    get_latest_firmware,
    get_all_firmware_versions,
    update_firmware_statistics,
    deprecate_firmware_version,
    compare_versions,
)


class FirmwareService:
    """Service for managing firmware files and metadata."""

    @staticmethod
    def calculate_checksums(file_data: bytes) -> tuple[str, str]:
        """Calculate MD5 and SHA256 checksums for firmware data.

        Args:
            file_data: Firmware binary data

        Returns:
            Tuple of (md5_hex, sha256_hex)
        """
        md5_hash = hashlib.md5()
        sha256_hash = hashlib.sha256()

        md5_hash.update(file_data)
        sha256_hash.update(file_data)

        return (md5_hash.hexdigest(), sha256_hash.hexdigest())

    @staticmethod
    def upload_firmware(
        version: str,
        channel: str,
        file_data: bytes,
        release_notes: str | None = None,
        changelog: str | None = None,
        mandatory: bool = False,
        min_upgrade_version: str | None = None,
    ) -> FirmwareVersion:
        """Upload a new firmware version.

        Args:
            version: Semantic version string
            channel: Update channel (stable, beta, canary)
            file_data: Firmware binary data
            release_notes: Optional release notes
            changelog: Optional detailed changelog
            mandatory: Whether this is a mandatory update
            min_upgrade_version: Minimum version that can upgrade

        Returns:
            The created FirmwareVersion object

        Raises:
            ValueError: If version already exists or validation fails
        """
        # Check if version already exists
        existing = get_firmware_version(version)
        if existing:
            raise ValueError(f"Firmware version {version} already exists")

        # Validate semantic version format
        if not FirmwareService._is_valid_version(version):
            raise ValueError(f"Invalid semantic version format: {version}")

        # Validate channel
        if channel not in ["stable", "beta", "canary"]:
            raise ValueError(f"Invalid channel: {channel}")

        # Calculate checksums
        md5_checksum, sha256_checksum = FirmwareService.calculate_checksums(file_data)

        # Create firmware version in database
        firmware = create_firmware_version(
            version=version,
            channel=channel,
            file_data=file_data,
            file_size=len(file_data),
            md5_checksum=md5_checksum,
            sha256_checksum=sha256_checksum,
            release_notes=release_notes,
            changelog=changelog,
            mandatory=mandatory,
            min_upgrade_version=min_upgrade_version,
        )

        return firmware

    @staticmethod
    def get_firmware(version: str) -> FirmwareVersion | None:
        """Retrieve firmware by version string.

        Args:
            version: The version string

        Returns:
            The FirmwareVersion object or None if not found
        """
        return get_firmware_version(version)

    @staticmethod
    def get_firmware_by_id(firmware_id: int) -> FirmwareVersion | None:
        """Retrieve firmware by database ID.

        Args:
            firmware_id: The database ID

        Returns:
            The FirmwareVersion object or None if not found
        """
        return get_firmware_version_by_id(firmware_id)

    @staticmethod
    def get_latest_firmware(channel: str = "stable") -> FirmwareVersion | None:
        """Get the latest firmware for a channel.

        Args:
            channel: Update channel (default: stable)

        Returns:
            The latest FirmwareVersion object or None if not found
        """
        return get_latest_firmware(channel)

    @staticmethod
    def list_firmware(channel: str | None = None) -> list[FirmwareVersion]:
        """List all firmware versions, optionally filtered by channel.

        Args:
            channel: Optional channel to filter by

        Returns:
            List of FirmwareVersion objects
        """
        return get_all_firmware_versions(channel)

    @staticmethod
    def is_update_available(
        current_version: str,
        target_channel: str = "stable",
    ) -> FirmwareVersion | None:
        """Check if an update is available for the current version.

        Args:
            current_version: Current firmware version
            target_channel: Update channel to check

        Returns:
            FirmwareVersion if update available, None otherwise
        """
        latest = get_latest_firmware(target_channel)
        if not latest:
            return None

        # Compare versions
        if compare_versions(latest.version, current_version) > 0:
            return latest

        return None

    @staticmethod
    def record_download(firmware_id: int) -> bool:
        """Record a firmware download for statistics.

        Args:
            firmware_id: The firmware database ID

        Returns:
            True if recorded, False if firmware not found
        """
        return update_firmware_statistics(firmware_id, download_increment=True)

    @staticmethod
    def record_success(firmware_id: int) -> bool:
        """Record a successful firmware update for statistics.

        Args:
            firmware_id: The firmware database ID

        Returns:
            True if recorded, False if firmware not found
        """
        return update_firmware_statistics(firmware_id, success_increment=True)

    @staticmethod
    def record_failure(firmware_id: int) -> bool:
        """Record a failed firmware update for statistics.

        Args:
            firmware_id: The firmware database ID

        Returns:
            True if recorded, False if firmware not found
        """
        return update_firmware_statistics(firmware_id, failure_increment=True)

    @staticmethod
    def deprecate(version: str) -> bool:
        """Deprecate a firmware version.

        Args:
            version: The version string to deprecate

        Returns:
            True if deprecated, False if not found
        """
        return deprecate_firmware_version(version)

    @staticmethod
    def generate_download_url(firmware_version: str, base_url: str) -> str:
        """Generate a download URL for firmware.

        Args:
            firmware_version: The firmware version
            base_url: Base URL for the API

        Returns:
            The download URL
        """
        return f"{base_url}/api/firmware/download/{firmware_version}"

    @staticmethod
    def _is_valid_version(version: str) -> bool:
        """Validate semantic version format.

        Args:
            version: Version string to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            parts = version.split(".")
            if len(parts) < 2:
                return False
            for part in parts:
                int(part)
            return True
        except ValueError:
            return False
