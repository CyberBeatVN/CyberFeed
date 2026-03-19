"""Article schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TagRead(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class CategoryRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    color: str | None
    icon: str | None

    model_config = {"from_attributes": True}


class ArticleRead(BaseModel):
    id: uuid.UUID
    title: str
    url: str
    content: str | None
    summary: str | None
    summary_method: str | None
    source_name: str
    source_platform: str
    author: str | None
    image_url: str | None
    published_at: datetime | None
    collected_at: datetime
    is_read: bool
    is_bookmarked: bool
    category: CategoryRead | None = None
    tags: list[TagRead] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleUpdate(BaseModel):
    is_read: bool | None = None
    is_bookmarked: bool | None = None
    category_id: uuid.UUID | None = None
    tags: list[str] | None = None


class ArticleListResponse(BaseModel):
    articles: list[ArticleRead]
    total: int
    page: int
    pages: int


class ArticleSearchParams(BaseModel):
    q: str | None = None
    platform: str | None = None
    source_id: uuid.UUID | None = None
    category: str | None = None
    tag: str | None = None
    is_read: bool | None = None
    is_bookmarked: bool | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    sort: str = "collected_at"
