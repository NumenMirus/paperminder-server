"""Custom exceptions for PaperMinder application."""


class RecipientNotConnectedError(RuntimeError):
    """Raised when a sender attempts to reach a recipient without active connections."""


class RecipientNotFoundError(RuntimeError):
    """Raised when attempting to send a message to a non-existent recipient."""