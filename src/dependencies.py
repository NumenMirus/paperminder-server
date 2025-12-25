"""Dependency functions for FastAPI routes."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from authx import RequestToken

from src.config import auth
from src.crud import get_user


async def get_bearer_token(
    authorization: Annotated[str, Header()]
) -> RequestToken:
    """Extract and verify JWT token from Authorization header.

    This dependency extracts the bearer token from the Authorization header
    and verifies it without exposing AuthX's internal configuration parameters.

    Args:
        authorization: The raw Authorization header value (e.g., "Bearer <token>")

    Returns:
        The verified token payload as RequestToken

    Raises:
        HTTPException 401: If token is missing, malformed, or invalid
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    # Extract token from "Bearer <token>" format
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <token>'",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use 'Bearer <token>'",
        )

    # Decode and verify token
    try:
        payload = auth._decode_token(token)
        auth.verify_token(payload)
        return payload
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from e


async def get_current_user(
    token: RequestToken = Depends(get_bearer_token),
) -> RequestToken:
    """Dependency to get the current authenticated user.

    Args:
        token: JWT token from Authorization header

    Returns:
        The verified token payload

    Raises:
        HTTPException 401: If token is invalid
    """
    return token


async def get_current_admin_user(
    token: RequestToken = Depends(get_bearer_token),
) -> RequestToken:
    """Dependency to verify the current user is an admin.

    Args:
        token: JWT token from Authorization header

    Returns:
        The verified token payload

    Raises:
        HTTPException 401: If token is invalid
        HTTPException 403: If user is not an admin
    """
    user_uuid = token["uid"]

    # Get user from database
    user = get_user(uuid=user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Check if user is admin
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    return token


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[RequestToken, Depends(get_current_user)]
AdminUser = Annotated[RequestToken, Depends(get_current_admin_user)]
