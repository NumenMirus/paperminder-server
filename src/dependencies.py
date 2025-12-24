"""Dependency functions for FastAPI routes."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from authx import RequestToken

from src.config import auth
from src.crud import get_user


async def get_current_user(
    token: RequestToken = Depends(auth.get_token_from_request),
) -> RequestToken:
    """Dependency to get the current authenticated user.

    Args:
        token: JWT token from request

    Returns:
        The verified token payload

    Raises:
        HTTPException 401: If token is invalid
    """
    auth.verify_token(token=token)
    return token


async def get_current_admin_user(
    token: Annotated[RequestToken, Depends(auth.get_token_from_request)],
) -> RequestToken:
    """Dependency to verify the current user is an admin.

    Args:
        token: JWT token from request

    Returns:
        The verified token payload

    Raises:
        HTTPException 401: If token is invalid
        HTTPException 403: If user is not an admin
    """
    auth.verify_token(token=token)
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
