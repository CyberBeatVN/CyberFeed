"""Articles API: CRUD, search, summarize."""

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from cyberfeed.api.deps import get_current_user, get_db, require_role
from cyberfeed.core.exceptions import NotFoundError
from cyberfeed.models.user import User
from cyberfeed.schemas.article import ArticleListResponse, ArticleRead, ArticleUpdate
from cyberfeed.services.article_service import ArticleService
from cyberfeed.services.summary_service import SummaryService

router = APIRouter(prefix="/articles", tags=["articles"])
article_service = ArticleService()
summary_service = SummaryService()


@router.get("", response_model=ArticleListResponse)
async def list_articles(
    q: str | None = None,
    platform: str | None = None,
    source_id: uuid.UUID | None = None,
    category: str | None = None,
    tag: str | None = None,
    is_read: bool | None = None,
    is_bookmarked: bool | None = None,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    sort: str = "collected_at",
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleListResponse:
    articles, total = await article_service.search(
        db,
        q=q,
        platform=platform,
        source_id=source_id,
        category_slug=category,
        tag_name=tag,
        is_read=is_read,
        is_bookmarked=is_bookmarked,
        page=page,
        per_page=per_page,
        sort=sort,
    )
    return ArticleListResponse(
        articles=[ArticleRead.model_validate(a) for a in articles],
        total=total,
        page=page,
        pages=math.ceil(total / per_page) if total > 0 else 1,
    )


@router.get("/{article_id}", response_model=ArticleRead)
async def get_article(
    article_id: uuid.UUID,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleRead:
    article = await article_service.get_by_id(db, article_id)
    if not article:
        raise NotFoundError("Article")
    return ArticleRead.model_validate(article)


@router.patch("/{article_id}", response_model=ArticleRead)
async def update_article(
    article_id: uuid.UUID,
    body: ArticleUpdate,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleRead:
    article = await article_service.get_by_id(db, article_id)
    if not article:
        raise NotFoundError("Article")

    if body.is_read is not None:
        article.is_read = body.is_read
    if body.is_bookmarked is not None:
        article.is_bookmarked = body.is_bookmarked
    if body.category_id is not None:
        article.category_id = body.category_id

    if body.tags is not None:
        article.tags.clear()
        await article_service._link_tags(db, article, body.tags)

    await db.flush()
    return ArticleRead.model_validate(article)


@router.post("/{article_id}/summarize", response_model=ArticleRead)
async def summarize_article(
    article_id: uuid.UUID,
    force: bool = False,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ArticleRead:
    article = await article_service.get_by_id(db, article_id)
    if not article:
        raise NotFoundError("Article")
    article = await summary_service.summarize(db, article, force=force)
    return ArticleRead.model_validate(article)


@router.post("/summarize-batch")
async def summarize_batch(
    article_ids: list[uuid.UUID],
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    articles = []
    for aid in article_ids[:50]:  # limit to 50
        a = await article_service.get_by_id(db, aid)
        if a:
            articles.append(a)
    processed, failed = await summary_service.summarize_batch(db, articles)
    return {"processed": processed, "failed": failed}


@router.delete("/{article_id}", status_code=204)
async def delete_article(
    article_id: uuid.UUID,
    _user: User = Depends(require_role("admin", "editor")),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await article_service.delete(db, article_id)
    if not deleted:
        raise NotFoundError("Article")
