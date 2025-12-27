"""Business logic for websocket messaging between PaperMinder clients."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import WebSocket

from src.services import MessageService
from src.models.message import InboundMessage, OutboundMessage, StatusMessage, SubscriptionRequest
from src.crud import get_and_increment_daily_message_number
from src.exceptions import RecipientNotConnectedError, RecipientNotFoundError
from src.services.update_service import UpdateService
from src.config import get_settings


class ConnectionManager:
    """Tracks websocket connections and orchestrates message routing."""

    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._subscriptions: Dict[int, SubscriptionRequest] = {}
        self._logger = logging.getLogger(__name__)

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[user_id].append(websocket)

    async def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            sockets = self._connections.get(user_id)
            if not sockets:
                return
            if websocket in sockets:
                sockets.remove(websocket)
                self._subscriptions.pop(id(websocket), None)
            if not sockets:
                self._connections.pop(user_id, None)

    async def register_subscription(self, websocket: WebSocket, subscription: SubscriptionRequest) -> None:
        """Register a printer subscription and handle firmware info."""
        async with self._lock:
            self._subscriptions[id(websocket)] = subscription

        # Update printer firmware and connection info
        await asyncio.to_thread(
            UpdateService.update_printer_subscription_info,
            printer_uuid=str(subscription.api_key),  # api_key is used as printer UUID
            firmware_version=subscription.firmware_version,
            platform=subscription.platform,
            auto_update=subscription.auto_update,
            update_channel=subscription.update_channel,
            online=True,
        )

        # Check for available firmware updates
        if subscription.auto_update:
            await self._check_and_push_update(websocket, subscription)

    async def _check_and_push_update(self, websocket: WebSocket, subscription: SubscriptionRequest) -> None:
        """Check for firmware updates and push to printer if available."""
        try:
            printer_uuid = str(subscription.api_key)  # api_key is used as printer UUID
            firmware = await asyncio.to_thread(
                UpdateService.check_for_updates,
                printer_uuid,
            )

            if firmware:
                # Get base URL for firmware downloads
                settings = get_settings()
                base_url = getattr(settings, 'base_url', 'http://localhost:8000')

                # Create firmware update message
                update_message = await asyncio.to_thread(
                    UpdateService.create_firmware_update_message,
                    firmware,
                    base_url,
                )

                # Push update to printer
                import json
                await websocket.send_text(json.dumps(update_message))

                # Record update start
                await asyncio.to_thread(
                    UpdateService.record_update_start,
                    printer_uuid,
                    firmware.version,
                )

                self._logger.info(f"Pushed firmware update {firmware.version} to printer {printer_uuid}")
        except Exception as e:
            self._logger.exception(f"Failed to check/push firmware update: {e}")

    async def send_firmware_update(self, printer_uuid: str, update_message: dict) -> bool:
        """Send a firmware update message to a specific printer.

        Args:
            printer_uuid: The printer UUID
            update_message: The firmware update message dictionary

        Returns:
            True if sent, False if printer not connected
        """
        async with self._lock:
            sockets = list(self._connections.get(printer_uuid, []))

        if not sockets:
            return False

        import json
        payload = json.dumps(update_message)
        for socket in sockets:
            await socket.send_text(payload)
            self._logger.debug(f"Sent firmware update to {printer_uuid}: {payload}")

        return True

    def is_printer_connected(self, printer_uuid: str) -> bool:
        """Check if a printer is currently connected.

        Args:
            printer_uuid: The printer UUID

        Returns:
            True if printer has active connections, False otherwise
        """
        return len(self._connections.get(printer_uuid, [])) > 0

    async def handle_firmware_progress(self, printer_uuid: str, percent: int, status_message: str) -> None:
        """Handle firmware update progress from printer."""
        try:
            await asyncio.to_thread(
                UpdateService.handle_firmware_progress,
                printer_uuid,
                percent,
                status_message,
            )
        except Exception as e:
            self._logger.exception(f"Failed to handle firmware progress: {e}")

    async def handle_firmware_complete(self, printer_uuid: str, version: str) -> None:
        """Handle successful firmware update completion."""
        try:
            await asyncio.to_thread(
                UpdateService.handle_firmware_complete,
                printer_uuid,
                version,
            )
            self._logger.info(f"Printer {printer_uuid} successfully updated to firmware {version}")
        except Exception as e:
            self._logger.exception(f"Failed to handle firmware complete: {e}")

    async def handle_firmware_failed(self, printer_uuid: str, error_message: str) -> None:
        """Handle firmware update failure."""
        try:
            await asyncio.to_thread(
                UpdateService.handle_firmware_failed,
                printer_uuid,
                error_message,
            )
            self._logger.warning(f"Printer {printer_uuid} firmware update failed: {error_message}")
        except Exception as e:
            self._logger.exception(f"Failed to handle firmware failed: {e}")

    async def handle_firmware_declined(self, printer_uuid: str, version: str, auto_update: bool) -> None:
        """Handle firmware update declined by printer."""
        try:
            await asyncio.to_thread(
                UpdateService.handle_firmware_declined,
                printer_uuid,
                version,
            )
            if not auto_update:
                self._logger.info(f"Printer {printer_uuid} declined firmware update {version} (auto_update disabled)")
            else:
                self._logger.warning(f"Printer {printer_uuid} declined firmware update {version}")
        except Exception as e:
            self._logger.exception(f"Failed to handle firmware declined: {e}")

    def subscription_for(self, websocket: WebSocket) -> Optional[SubscriptionRequest]:
        return self._subscriptions.get(id(websocket))

    async def send_personal_message(self, sender_id: str, message: InboundMessage) -> None:
        recipient_key = str(message.recipient_id)
        async with self._lock:
            recipients = list(self._connections.get(recipient_key, []))

        # Sanitize the message
        sanitized_sender_name, sanitized_message_body = MessageService.sanitize_incoming_message(
            message.sender_name or sender_id, message.message
        )

        # Get the next daily message number for the recipient
        daily_number = await asyncio.to_thread(
            get_and_increment_daily_message_number,
            recipient_key
        )

        outbound = OutboundMessage(
            sender_name=sanitized_sender_name,
            message=sanitized_message_body,
            daily_number=daily_number,
        )
        payload = outbound.model_dump_json()

        # If recipients are online, send the message
        if recipients:
            for websocket in recipients:
                await websocket.send_text(payload)
                self._logger.debug(f"Sent to {recipient_key}: {payload}")
        else:
            # Cache the message for when the recipient comes back online
            try:
                await asyncio.to_thread(
                    MessageService.cache_message_fn,
                    recipient_id=recipient_key,
                    sender_id=sender_id,
                    sender_name=sanitized_sender_name,
                    message_body=sanitized_message_body,
                )
            except Exception:
                self._logger.exception("Failed to cache message")
            raise RecipientNotConnectedError(recipient_key)

        try:
            await asyncio.to_thread(MessageService.persist_log, sender_id=sender_id, message=message)
        except Exception:  # pragma: no cover - logging should not interrupt delivery
            self._logger.exception("Failed to persist message log")

    async def notify(self, websocket: WebSocket, status: StatusMessage) -> None:
        payload = status.model_dump_json()
        await websocket.send_text(payload)
        # Skip logging for ping/pong keep-alive status messages
        if status.code not in ["ping", "pong"]:
            self._logger.debug(f"Sent status message: {payload}")

    async def send_cached_messages(self, user_id: str, websocket: WebSocket) -> None:
        """Send all cached messages to a user who just came online."""
        try:
            cached_messages = await asyncio.to_thread(MessageService.get_cached_messages_fn, user_id)

            if cached_messages:
                for cached in cached_messages:
                    # Get the next daily message number for each cached message
                    daily_number = await asyncio.to_thread(
                        get_and_increment_daily_message_number,
                        user_id
                    )
                    outbound = OutboundMessage(
                        sender_name=cached.sender_name,
                        message=cached.message_body,
                        timestamp=cached.created_at,
                        daily_number=daily_number,
                    )
                    payload = outbound.model_dump_json()
                    await websocket.send_text(payload)
                    self._logger.debug(f"Sent cached message to {user_id}: {payload}")

                # Mark all cached messages as delivered
                await asyncio.to_thread(MessageService.mark_as_delivered, user_id)
                self._logger.info(f"Sent {len(cached_messages)} cached messages to user {user_id}")
        except Exception:
            self._logger.exception(f"Failed to send cached messages to user {user_id}")

    def count_active(self, user_id: str) -> int:
        return len(self._connections.get(user_id, []))

    def has_active_user(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))


# Single shared manager instance reused by HTTP and websocket routes.
connection_manager = ConnectionManager()
