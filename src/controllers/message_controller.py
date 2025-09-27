"""Business logic for websocket messaging between PaperMinder clients."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import WebSocket

from src.models.message import InboundMessage, OutboundMessage, StatusMessage, SubscriptionRequest


class RecipientNotConnectedError(RuntimeError):
    """Raised when a sender attempts to reach a recipient without active connections."""


class ConnectionManager:
    """Tracks websocket connections and orchestrates message routing."""

    def __init__(self) -> None:
        self._connections: Dict[str, List[WebSocket]] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._subscriptions: Dict[int, SubscriptionRequest] = {}

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
        if not recipients:
            raise RecipientNotConnectedError(recipient_key)

        outbound = OutboundMessage(
            sender_name=message.sender_name or sender_id,
            message=message.message,
        )
        payload = outbound.model_dump_json()
        for websocket in recipients:
            await websocket.send_text(payload)

    async def notify(self, websocket: WebSocket, status: StatusMessage) -> None:
        await websocket.send_text(status.model_dump_json())

    def count_active(self, user_id: str) -> int:
        return len(self._connections.get(user_id, []))

    def has_active_user(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))
