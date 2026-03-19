"""Tags API: CRUD and article tagging."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.api.deps import get_current_user, get_db, require_role
from cyberfeed.core.exceptions import NotFoundError
from cyberfeed.models.article import Tag, article_tags
from cyberfeed.models.user import User
from cyberfeed.schemas.category import TagCreate, TagRead

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("")
async def list_tags(
    q: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    query = (
        select(Tag, func.count(article_tags.c.article_id).label("article_count"))
        .outerjoin(article_tags, article_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(article_tags.c.article_id).desc())
        .limit(limit)
    )
    if q:
        query = query.where(Tag.name.ilike(f"%{q}%"))

    result = await db.execute(query)
    tags = []
    for row in result.all():
        tag_data = TagRead.model_validate(row[0])
        tag_data.article_count = row[1]
        tags.append(tag_data)
    return {"tags": tags}


@router.get("/popular")
async def popular_tags(
    limit: int = Query(default=20, ge=1, le=50),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Tag, func.count(article_tags.c.article_id).label("cnt"))
        .join(article_tags, article_tags.c.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(article_tags.c.article_id).desc())
        .limit(limit)
    )
    tags = []
    for row in result.all():
        tag_data = TagRead.model_validate(row[0])
        tag_data.article_count = row[1]
        tags.append(tag_data)
    return {"tags": tags}


@router.post("")
async def create_tag(
    body: TagCreate,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TagRead:
    name = body.name.lower().strip()
    result = await db.execute(select(Tag).where(Tag.name == name))
    existing = result.scalar_one_or_none()
    if existing:
        return TagRead.model_validate(existing)

    tag = Tag(name=name)
    db.add(tag)
    await db.flush()
    return TagRead.model_validate(tag)


@router.delete("/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: uuid.UUID,
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(Tag).where(Tag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise NotFoundError("Tag")
    await db.delete(tag)
