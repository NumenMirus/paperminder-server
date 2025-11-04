"""Service layer for printer-related business logic."""

from __future__ import annotations

from src.database import Printer, session_scope
from src.crud import (
    register_printer,
    get_all_registered_printers,
    delete_printer,
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
