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
from src.utils import MessageSanitizer


class MessageService:
    """Service for managing message operations and caching."""

    @staticmethod
    def sanitize_incoming_message(sender_name: str, message_body: str) -> tuple[str, str]:
        """Sanitize incoming message content.
        
        Args:
            sender_name: Name of the message sender
            message_body: The message content
            
        Returns:
            Tuple of (sanitized_sender_name, sanitized_message_body)
        """
        return (
            MessageSanitizer.sanitize_name(sender_name),
            MessageSanitizer.sanitize_message(message_body),
        )

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
        # Sanitize the message before caching
        sanitized_sender_name, sanitized_message_body = MessageService.sanitize_incoming_message(
            sender_name, message_body
        )
        return cache_message(recipient_id, sender_id, sanitized_sender_name, sanitized_message_body)

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
        # Create a sanitized copy of the message before logging
        sanitized_sender_name, sanitized_message_body = MessageService.sanitize_incoming_message(
            message.sender_name, message.message
        )
        
        # Create a modified message with sanitized content
        sanitized_message = InboundMessage(
            recipient_id=message.recipient_id,
            sender_name=sanitized_sender_name,
            message=sanitized_message_body,
        )
        persist_message_log(sender_id, sanitized_message)

    @staticmethod
    def cleanup_old_cache(days: int = 7) -> int:
        """Delete cached messages older than specified days.
        
        Args:
            days: Number of days to keep (default 7)
            
        Returns:
            Count of messages deleted
        """
        return clear_old_cached_messages(days)
