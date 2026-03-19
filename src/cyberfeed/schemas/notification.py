"""Notification rule schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NotificationRuleCreate(BaseModel):
    channel: str = Field(max_length=20)
    destination: str = Field(max_length=500)
    keywords: list[str] = Field(default_factory=list)
    category_ids: list[uuid.UUID] = Field(default_factory=list)
    source_platforms: list[str] = Field(default_factory=list)
    is_active: bool = True


class NotificationRuleRead(BaseModel):
    id: uuid.UUID
    channel: str
    destination: str
    keywords: list
    category_ids: list
    source_platforms: list
    is_active: bool
    last_sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationRuleUpdate(BaseModel):
    keywords: list[str] | None = None
    category_ids: list[uuid.UUID] | None = None
    source_platforms: list[str] | None = None
    is_active: bool | None = None
    destination: str | None = Field(default=None, max_length=500)


class NotificationTestRequest(BaseModel):
    channel: str = Field(max_length=20)
    destination: str = Field(max_length=500)
