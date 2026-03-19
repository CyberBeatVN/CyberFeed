"""Category and tag schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CategoryCreate(BaseModel):
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    color: str | None = Field(default=None, max_length=7)
    icon: str | None = Field(default=None, max_length=50)
    sort_order: int | None = None


class CategoryReadWithCount(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    color: str | None
    icon: str | None
    sort_order: int
    article_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class TagRead(BaseModel):
    id: uuid.UUID
    name: str
    article_count: int = 0

    model_config = {"from_attributes": True}


class TagCreate(BaseModel):
    name: str = Field(max_length=100)
