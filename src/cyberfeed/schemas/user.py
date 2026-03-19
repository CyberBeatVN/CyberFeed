"""User and auth schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = Field(default=None, max_length=255)


class UserRead(BaseModel):
    id: uuid.UUID
    username: str
    email: str | None
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None


class LoginRequest(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105


class RefreshRequest(BaseModel):
    refresh_token: str
