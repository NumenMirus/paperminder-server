"""Utilities for sanitizing message content."""

import re
import unicodedata


class MessageSanitizer:
    """Sanitize incoming messages by removing or replacing unprintable characters."""

    # Characters that are safe for printing
    SAFE_CONTROL_CHARS = {'\n', '\r', '\t'}
    
    # Character mapping for non-ASCII to ASCII equivalents
    CHAR_MAP = {
        'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a',
        'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e',
        'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i',
        'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o', 'ø': 'o',
        'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u',
        'ý': 'y', 'ÿ': 'y',
        'ñ': 'n',
        'ç': 'c',
        'æ': 'ae',
        'ß': 'ss',
        'Å': 'A', 'Ä': 'A', 'Á': 'A', 'À': 'A', 'Â': 'A', 'Ã': 'A',
        'È': 'E', 'É': 'E', 'Ê': 'E', 'Ë': 'E',
        'Ì': 'I', 'Í': 'I', 'Î': 'I', 'Ï': 'I',
        'Ò': 'O', 'Ó': 'O', 'Ô': 'O', 'Õ': 'O', 'Ö': 'O', 'Ø': 'O',
        'Ù': 'U', 'Ú': 'U', 'Û': 'U', 'Ü': 'U',
        'Ý': 'Y',
        'Ñ': 'N',
        'Ç': 'C',
        'Æ': 'AE',
    }

    @staticmethod
    def sanitize(text: str, replace_with: str | None = None) -> str:
        """Remove or replace unprintable characters from text.
        
        Args:
            text: The text to sanitize
            replace_with: Character to replace unprintable chars with (default: remove)
                         If None, unprintable chars are removed
                         If string, unprintable chars are replaced with this string
            
        Returns:
            Sanitized text with unprintable characters removed or replaced
        """
        if not text:
            return text
        
        # Handle null characters explicitly
        text = text.replace('\x00', '')
        
        sanitized = []
        for char in text:
            if MessageSanitizer._is_printable(char):
                sanitized.append(char)
            elif char in MessageSanitizer.CHAR_MAP:
                # Replace with ASCII equivalent
                sanitized.append(MessageSanitizer.CHAR_MAP[char])
            elif replace_with is not None:
                sanitized.append(replace_with)
            # else: skip the character (remove it)
        
        return ''.join(sanitized)

    @staticmethod
    def _is_printable(char: str) -> bool:
        """Check if a character is printable or an allowed control character.
        
        Args:
            char: Single character to check
            
        Returns:
            True if character is safe to print, False otherwise
        """
        # Allow specific control characters
        if char in MessageSanitizer.SAFE_CONTROL_CHARS:
            return True
        
        # Only allow ASCII printable characters (32-126)
        # This includes letters, numbers, punctuation, and common symbols
        # Rejects non-ASCII characters like emojis, accented characters, etc.
        if ord(char) >= 32 and ord(char) <= 126:
            return True
        
        return False

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Sanitize a name/identifier field.
        
        Args:
            name: The name to sanitize
            
        Returns:
            Sanitized name with unprintable characters removed
        """
        # For names, be more strict - remove most control chars and replace with space
        sanitized = MessageSanitizer.sanitize(name, replace_with=' ')
        # Remove extra whitespace
        sanitized = ' '.join(sanitized.split())
        return sanitized

    @staticmethod
    def sanitize_message(message: str) -> str:
        """Sanitize message content.
        
        Args:
            message: The message to sanitize
            
        Returns:
            Sanitized message with unprintable characters removed
        """
        # For messages, preserve newlines but remove other control chars
        return MessageSanitizer.sanitize(message)
