"""Source schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    name: str = Field(max_length=200)
    platform: str = Field(max_length=50)
    config: dict
    collect_interval_min: int = Field(default=30, ge=5, le=1440)
    category_ids: list[uuid.UUID] | None = None


class SourceRead(BaseModel):
    id: uuid.UUID
    name: str
    platform: str
    config: dict  # masked sensitive fields
    is_active: bool
    collect_interval_min: int
    last_collected_at: datetime | None
    last_error: str | None
    error_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    config: dict | None = None
    is_active: bool | None = None
    collect_interval_min: int | None = Field(default=None, ge=5, le=1440)
    category_ids: list[uuid.UUID] | None = None
