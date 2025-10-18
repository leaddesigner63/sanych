"""Pydantic schemas for admin user management endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from ..models.core import UserRole


class UserCreateRequest(BaseModel):
    """Payload for creating a new user in the admin interface."""

    username: str
    role: UserRole = UserRole.USER
    telegram_id: int | None = None
    quota_projects: int | None = None

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        username = value.strip()
        if not username:
            raise ValueError("Username must not be empty")
        return username

    @field_validator("quota_projects")
    @classmethod
    def validate_quota(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("Quota must be greater or equal to zero")
        return value

    @field_validator("telegram_id")
    @classmethod
    def validate_telegram_id(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Telegram id must be positive")
        return value


class UserUpdateRequest(BaseModel):
    """Fields that can be updated for an existing user."""

    username: str | None = None
    role: UserRole | None = None
    telegram_id: int | None = None
    quota_projects: int | None = None
    is_active: bool | None = None

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return value
        username = value.strip()
        if not username:
            raise ValueError("Username must not be empty")
        return username

    @field_validator("quota_projects")
    @classmethod
    def validate_quota(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("Quota must be greater or equal to zero")
        return value

    @field_validator("telegram_id")
    @classmethod
    def validate_telegram_id(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError("Telegram id must be positive")
        return value


class UserResponse(BaseModel):
    """Serialized representation of the user model for API responses."""

    id: int
    username: str
    role: UserRole
    telegram_id: int | None
    quota_projects: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, use_enum_values=False)


__all__ = ["UserCreateRequest", "UserUpdateRequest", "UserResponse"]
