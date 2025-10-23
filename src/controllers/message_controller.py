"""Business logic for websocket messaging between PaperMinder clients."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import WebSocket

from src.services import MessageService
from src.models.message import InboundMessage, OutboundMessage, StatusMessage, SubscriptionRequest


class RecipientNotConnectedError(RuntimeError):
    """Raised when a sender attempts to reach a recipient without active connections."""


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
        async with self._lock:
            self._subscriptions[id(websocket)] = subscription

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
        
        outbound = OutboundMessage(
            sender_name=sanitized_sender_name,
            message=sanitized_message_body,
        )
        payload = outbound.model_dump_json()
        
        # If recipients are online, send the message
        if recipients:
            for websocket in recipients:
                await websocket.send_text(payload)
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
        await websocket.send_text(status.model_dump_json())

    async def send_cached_messages(self, user_id: str, websocket: WebSocket) -> None:
        """Send all cached messages to a user who just came online."""
        try:
            cached_messages = await asyncio.to_thread(MessageService.get_cached_messages_fn, user_id)
            
            if cached_messages:
                for cached in cached_messages:
                    outbound = OutboundMessage(
                        sender_name=cached.sender_name,
                        message=cached.message_body,
                        timestamp=cached.created_at,
                    )
                    await websocket.send_text(outbound.model_dump_json())
                
                # Mark all cached messages as delivered
                await asyncio.to_thread(MessageService.mark_as_delivered, user_id)
                self._logger.info(f"Sent {len(cached_messages)} cached messages to user {user_id}")
        except Exception:
            self._logger.exception(f"Failed to send cached messages to user {user_id}")

    def count_active(self, user_id: str) -> int:
        return len(self._connections.get(user_id, []))

    def has_active_user(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))
