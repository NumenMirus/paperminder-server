from fastapi import APIRouter, Depends, HTTPException, status
from authx import RequestToken
from uuid import UUID
from src.config import auth
from src.models.auth import (
    UserRegistrationRequest,
    UserLoginRequest,
    UserRegistrationResponse,
    UserLoginResponse,
    UserResponse,
)
from src.crud import (
    create_user,
    get_user_by_username,
    get_user_by_email,
    verify_user_password,
    get_user,
)
from src.dependencies import get_bearer_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserRegistrationRequest) -> UserRegistrationResponse:
    """Register a new user account.
    
    Args:
        payload: Registration request with username, email, password, and optional metadata
        
    Returns:
        UserRegistrationResponse with user data and JWT tokens
        
    Raises:
        HTTPException 400: If username or email already exists
    """
    # Check if username already exists
    if get_user_by_username(payload.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )
    
    # Check if email already exists
    if get_user_by_email(payload.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create the user
    try:
        user = create_user(
            username=payload.username,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            phone=payload.phone,
            is_admin=False,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account",
        ) from e

    # Generate tokens with is_admin claim
    access_token = auth.create_access_token(uid=user.uuid, payload={"is_admin": user.is_admin})
    refresh_token = auth.create_refresh_token(uid=user.uuid, payload={"is_admin": user.is_admin})

    # Build response
    user_response = UserResponse(
        uuid=UUID(user.uuid),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )
    
    return UserRegistrationResponse(
        user=user_response,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", status_code=status.HTTP_200_OK)
def login(payload: UserLoginRequest) -> UserLoginResponse:
    """Login a user with username and password.
    
    Args:
        payload: Login request with username and password
        
    Returns:
        UserLoginResponse with user data and JWT tokens
        
    Raises:
        HTTPException 401: If credentials are invalid
    """
    # Verify credentials
    if not verify_user_password(payload.username, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    
    # Get user
    user = get_user_by_username(payload.username)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is not active",
        )

    # Generate tokens with is_admin claim
    access_token = auth.create_access_token(uid=user.uuid, payload={"is_admin": user.is_admin})
    refresh_token = auth.create_refresh_token(uid=user.uuid, payload={"is_admin": user.is_admin})

    # Build response
    user_response = UserResponse(
        uuid=UUID(user.uuid),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )
    
    return UserLoginResponse(
        user=user_response,
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/me", status_code=status.HTTP_200_OK)
def get_user_info(token: RequestToken = Depends(get_bearer_token)):
    """Get information about the currently authenticated user.

    Requires authentication via JWT token in Authorization header.

    Returns:
        UserResponse with user data

    Raises:
        HTTPException 401: If token is invalid or expired
        HTTPException 404: If user not found
    """
    try:
        # Extract user UUID from token payload
        # TokenPayload is a Pydantic model with .sub attribute (JWT subject claim)
        user_uuid = token.sub
    except AttributeError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing uid",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from e
    
    # Get user from database
    user = get_user(uuid=user_uuid)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return UserResponse(
        uuid=UUID(user.uuid),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
    )