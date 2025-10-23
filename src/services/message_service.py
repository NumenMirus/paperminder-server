"""Service layer for message-related business logic."""

from __future__ import annotations

from src.database import (
    MessageCache,
    persist_message_log,
    cache_message,
    get_cached_messages,
    mark_cached_messages_as_delivered,
    clear_old_cached_messages,
)
from src.models.message import InboundMessage


class MessageService:
    """Service for managing message operations and caching."""

    @staticmethod
    def cache_message_fn(recipient_id: str, sender_id: str, sender_name: str, message_body: str) -> MessageCache:
        """Cache a message for a recipient who may be offline.
        
        Args:
            recipient_id: ID of the recipient
            sender_id: ID of the sender
            sender_name: Display name of the sender
            message_body: The message content
            
        Returns:
            The cached MessageCache object
        """
        return cache_message(recipient_id, sender_id, sender_name, message_body)

    @staticmethod
    def get_cached_messages_fn(recipient_id: str) -> list[MessageCache]:
        """Retrieve all undelivered cached messages for a recipient.
        
        Args:
            recipient_id: ID of the recipient
            
        Returns:
            List of undelivered MessageCache objects
        """
        return get_cached_messages(recipient_id)

    @staticmethod
    def mark_as_delivered(recipient_id: str) -> int:
        """Mark all cached messages for a recipient as delivered.
        
        Args:
            recipient_id: ID of the recipient
            
        Returns:
            Count of messages marked as delivered
        """
        return mark_cached_messages_as_delivered(recipient_id)

    @staticmethod
    def persist_log(sender_id: str, message: InboundMessage) -> None:
        """Persist a delivered message to the message log.
        
        Args:
            sender_id: ID of the sender
            message: The InboundMessage object to log
        """
        persist_message_log(sender_id, message)

    @staticmethod
    def cleanup_old_cache(days: int = 7) -> int:
        """Delete cached messages older than specified days.
        
        Args:
            days: Number of days to keep (default 7)
            
        Returns:
            Count of messages deleted
        """
        return clear_old_cached_messages(days)
