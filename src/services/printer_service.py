"""Service layer for printer-related business logic."""

from __future__ import annotations

from src.database import Printer, session_scope
from src.crud import (
    register_printer,
    get_all_registered_printers,
    delete_printer,
    add_printer_to_group,
    remove_printer_from_group,
    get_printer_groups,
    is_printer_in_group,
)


class PrinterService:
    """Service for managing printer operations."""

    @staticmethod
    def register(name: str, uuid: str, location: str, user_uuid: str) -> Printer:
        """Register a new printer in the system."""
        return register_printer(name, uuid, location, user_uuid)

    @staticmethod
    async def get_all() -> list[Printer]:
        """Retrieve all registered printers."""
        return await get_all_registered_printers()

    @staticmethod
    def delete(uuid: str) -> bool:
        """Delete a printer by UUID."""
        return delete_printer(uuid)

    @staticmethod
    def exists(uuid: str) -> bool:
        """Check if a printer with the given UUID exists."""
        with session_scope() as session:
            printer = session.query(Printer).filter_by(uuid=uuid).first()
            return printer is not None

    @staticmethod
    def add_to_group(printer_uuid: str, group_uuid: str) -> bool:
        """Add a printer to a group.
        
        Args:
            printer_uuid: The UUID of the printer
            group_uuid: The UUID of the group
            
        Returns:
            True if the printer was added to the group, False if already in group or not found
        """
        # Check if already in group
        if is_printer_in_group(printer_uuid, group_uuid):
            return False
        
        try:
            add_printer_to_group(printer_uuid, group_uuid)
            return True
        except Exception:
            return False

    @staticmethod
    def remove_from_group(printer_uuid: str, group_uuid: str) -> bool:
        """Remove a printer from a group.
        
        Args:
            printer_uuid: The UUID of the printer
            group_uuid: The UUID of the group
            
        Returns:
            True if the printer was removed from the group, False if not found
        """
        return remove_printer_from_group(printer_uuid, group_uuid)

    @staticmethod
    def get_printer_groups(printer_uuid: str) -> list:
        """Get all groups that a printer belongs to.
        
        Args:
            printer_uuid: The UUID of the printer
            
        Returns:
            List of Group objects that the printer belongs to
        """
        return get_printer_groups(printer_uuid)
