"""Pydantic models for authentication requests and responses."""

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class UserRegistrationRequest(BaseModel):
    """Request body for user registration."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern="^[a-zA-Z0-9_-]+$",
        description="Username (alphanumeric, underscore, hyphen only)",
    )
    email: str = Field(
        ...,
        description="Email address",
        json_schema_extra={"format": "email"},
    )
    password: str = Field(
        ...,
        min_length=4,
        max_length=16,
        description="Password (minimum 16 characters)",
    )
    full_name: str | None = Field(None, max_length=256, description="Full name (optional)")
    phone: str | None = Field(None, max_length=20, description="Phone number (optional)")

    @field_validator('username')
    @classmethod
    def transform_username_to_lowercase(cls, v: str) -> str:
        return v.lower()


class UserLoginRequest(BaseModel):
    """Request body for user login."""

    username: str = Field(..., min_length=2, description="Username")
    password: str = Field(..., min_length=4, description="Password")

    @field_validator('username')
    @classmethod
    def transform_username_to_lowercase(cls, v: str) -> str:
        return v.lower()


class UserResponse(BaseModel):
    """Response model for a user (public data only)."""

    uuid: UUID
    username: str
    email: str
    full_name: str | None
    phone: str | None
    is_active: bool
    created_at: datetime


class UserRegistrationResponse(BaseModel):
    """Response after successful user registration."""

    user: UserResponse
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")


class UserLoginResponse(BaseModel):
    """Response after successful user login."""

    user: UserResponse
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
