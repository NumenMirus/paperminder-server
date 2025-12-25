"""Dependency functions for FastAPI routes."""

import logging
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from authx import RequestToken

from src.config import auth
from src.crud import get_user


# Logger for authentication debugging
_auth_logger = logging.getLogger(__name__)


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
    _auth_logger.debug(f"get_bearer_token called, authorization header present: {bool(authorization)}")

    if not authorization:
        _auth_logger.error("Missing Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    # Extract token from "Bearer <token>" format
    try:
        scheme, token = authorization.split()
        _auth_logger.debug(f"Auth scheme: {scheme}, token length: {len(token)}")
        if scheme.lower() != "bearer":
            _auth_logger.error(f"Invalid auth scheme: {scheme}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Use 'Bearer <token>'",
            )
    except ValueError as e:
        _auth_logger.error(f"Failed to parse Authorization header: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Use 'Bearer <token>'",
        )

    # Decode and verify token
    try:
        _auth_logger.debug(f"Attempting to decode token (first 20 chars): {token[:20]}...")
        payload = auth._decode_token(token)
        _auth_logger.debug(f"Token decoded successfully, payload type: {type(payload)}")

        # auth._decode_token() already validates the token (signature, expiration, etc.)
        # No need to call auth.verify_token() separately - that would cause an error

        # Log the payload contents (safely)
        # TokenPayload is a Pydantic model with attributes, not a dict
        # Access the subject identifier (uid) from the payload
        try:
            uid = payload.sub  # JWT standard subject claim
            _auth_logger.info(f"Token validated for user uid: {uid}")
        except AttributeError:
            # Fallback: try to access as dict
            uid = payload.get("sub", "MISSING") if hasattr(payload, "get") else "UNKNOWN"
            _auth_logger.warning(f"Token payload has no 'sub' attribute, uid: {uid}, payload keys: {dir(payload)}")

        return payload
    except Exception as e:
        _auth_logger.exception(f"Token validation failed: {type(e).__name__}: {e}")
        _auth_logger.error(f"Token length was: {len(token)}, first 20 chars: {token[:20]}")
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
    _auth_logger.debug("get_current_admin_user called")

    # TokenPayload is a Pydantic model, access uid via .sub attribute
    user_uuid = token.sub
    _auth_logger.debug(f"Checking admin status for user uuid: {user_uuid}")

    # Get user from database
    user = get_user(uuid=user_uuid)
    if not user:
        _auth_logger.error(f"User not found in database: {user_uuid}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    _auth_logger.debug(f"User found: {user.username}, is_admin: {user.is_admin}")

    # Check if user is admin
    if not user.is_admin:
        _auth_logger.warning(f"User {user.username} is not an admin")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )

    _auth_logger.info(f"Admin user {user.username} authenticated successfully")
    return token


# Type aliases for cleaner dependency injection
CurrentUser = Annotated[RequestToken, Depends(get_current_user)]
AdminUser = Annotated[RequestToken, Depends(get_current_admin_user)]
