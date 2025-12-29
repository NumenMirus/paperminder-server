"""Custom exceptions for PaperMinder application."""


class RecipientNotConnectedError(RuntimeError):
    """Raised when a sender attempts to reach a recipient without active connections."""


class RecipientNotFoundError(RuntimeError):
    """Raised when attempting to send a message to a non-existent recipient."""


class BitmapProcessingError(RuntimeError):
    """Raised when bitmap image processing fails."""


class BitmapValidationError(RuntimeError):
    """Raised when bitmap validation fails."""