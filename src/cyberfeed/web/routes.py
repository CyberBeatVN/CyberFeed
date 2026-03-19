"""Web routes: server-rendered pages + HTMX partials."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from cyberfeed.config import get_settings
from cyberfeed.core.security import decode_token
from cyberfeed.database import async_session_factory
from cyberfeed.models.article import Article, Category, Tag
from cyberfeed.models.user import User
from cyberfeed.services.auth_service import AuthService

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = structlog.get_logger()
router = APIRouter()
auth_service = AuthService()

_template_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_template_dir))


def _timeago(dt: datetime) -> str:
    """Jinja2 filter: human-readable relative time."""
    if dt is None:
        return "unknown"
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        m = seconds // 60
        return f"{m}m ago"
    if seconds < 86400:
        h = seconds // 3600
        return f"{h}h ago"
    d = seconds // 86400
    if d == 1:
        return "yesterday"
    if d < 30:
        return f"{d}d ago"
    return dt.strftime("%b %d, %Y")


templates.env.filters["timeago"] = _timeago


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def _get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _get_optional_user(request: Request, db: AsyncSession = Depends(_get_db)) -> User | None:
    """Extract user from access_token cookie. Returns None if invalid."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user
    except Exception:
        return None
    return None


# ---------------------------------------------------------------------------
# Page routes (public)
# ---------------------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse, response_model=None)
async def login_page(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "registration_open": settings.REGISTRATION_OPEN, "error": None},
    )


@router.post("/login", response_class=HTMLResponse, response_model=None)
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(_get_db),
):
    settings = get_settings()
    try:
        _user, access_token, _refresh_token = await auth_service.login(db, username, password)
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=900,
        )
        return response
    except Exception as e:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "error": str(e),
                "registration_open": settings.REGISTRATION_OPEN,
            },
        )


@router.get("/register", response_class=HTMLResponse, response_model=None)
async def register_page(request: Request):
    settings = get_settings()
    if not settings.REGISTRATION_OPEN:
        return RedirectResponse("/login", status_code=302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse, response_model=None)
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    email: str = Form(None),
    db: AsyncSession = Depends(_get_db),
):
    settings = get_settings()
    if not settings.REGISTRATION_OPEN:
        return RedirectResponse("/login", status_code=302)
    try:
        _user, access_token, _refresh_token = await auth_service.register(
            db, username, password, email or None
        )
        response = RedirectResponse("/", status_code=302)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            max_age=900,
        )
        return response
    except Exception as e:
        return templates.TemplateResponse("register.html", {"request": request, "error": str(e)})


# ---------------------------------------------------------------------------
# Page routes (authenticated)
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse, response_model=None)
async def feed_page(
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return await _render_feed(request, db, user)


@router.get("/category/{slug}", response_class=HTMLResponse, response_model=None)
async def category_feed(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return await _render_feed(request, db, user, category_slug=slug)


@router.get("/tag/{name}", response_class=HTMLResponse, response_model=None)
async def tag_feed(
    name: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return await _render_feed(request, db, user, tag_name=name)


async def _render_feed(
    request: Request,
    db: AsyncSession,
    user: User,
    *,
    category_slug: str | None = None,
    tag_name: str | None = None,
) -> HTMLResponse:
    """Render the main feed page with sidebar data."""
    # Categories with counts
    cat_result = await db.execute(
        select(Category, func.count(Article.id).label("cnt"))
        .outerjoin(Article, Article.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.name)
    )
    categories = []
    category_color = None
    category_name = None
    for row in cat_result.all():
        cat = row[0]
        cat.article_count = row[1]
        categories.append(cat)
        if category_slug and cat.slug == category_slug:
            category_color = cat.color
            category_name = cat.name

    # Total article count
    total_result = await db.execute(select(func.count(Article.id)))
    total_articles = total_result.scalar() or 0

    # Popular tags
    tag_result = await db.execute(
        select(Tag)
        .join(Article.tags)
        .group_by(Tag.id)
        .order_by(func.count(Article.id).desc())
        .limit(15)
    )
    popular_tags = tag_result.scalars().all()

    # Articles for initial render
    articles, has_next = await _fetch_articles(db, category_slug=category_slug, tag_name=tag_name)

    return templates.TemplateResponse(
        "feed.html",
        {
            "request": request,
            "user": user,
            "categories": categories,
            "total_articles": total_articles,
            "popular_tags": popular_tags,
            "articles": articles,
            "has_next": has_next,
            "next_page": 2,
            "current_category": category_slug,
            "current_category_name": category_name,
            "category_color": category_color,
            "current_tag": tag_name,
            "q": None,
            "platform": None,
            "is_bookmarked": False,
            "category": category_slug,
            "tag": tag_name,
        },
    )


@router.get("/article/{article_id}", response_class=HTMLResponse, response_model=None)
async def article_page(
    article_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    try:
        aid = uuid.UUID(article_id)
    except ValueError:
        return RedirectResponse("/", status_code=302)

    result = await db.execute(
        select(Article)
        .options(selectinload(Article.tags), selectinload(Article.category))
        .where(Article.id == aid)
    )
    article = result.scalar_one_or_none()
    if not article:
        return RedirectResponse("/", status_code=302)

    return templates.TemplateResponse(
        "article.html", {"request": request, "user": user, "article": article}
    )


@router.get("/settings", response_class=HTMLResponse, response_model=None)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)

    from cyberfeed.models.notification import NotificationRule
    from cyberfeed.models.source import Source

    result = await db.execute(select(Source).order_by(Source.name))
    sources = result.scalars().all()

    # Categories with article counts for the Categories tab
    cat_result = await db.execute(
        select(Category, func.count(Article.id).label("cnt"))
        .outerjoin(Article, Article.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.sort_order, Category.name)
    )
    all_categories = []
    for row in cat_result.all():
        cat = row[0]
        cat.article_count = row[1]
        all_categories.append(cat)

    rules_result = await db.execute(
        select(NotificationRule)
        .where(NotificationRule.user_id == user.id)
        .order_by(NotificationRule.created_at)
    )
    notification_rules = rules_result.scalars().all()

    settings = get_settings()
    channels = []
    if settings.TELEGRAM_ENABLED:
        channels.append("telegram")
    if settings.EMAIL_ENABLED:
        channels.append("email")

    return templates.TemplateResponse(
        "settings.html",
        {
            "request": request,
            "user": user,
            "sources": sources,
            "all_categories": all_categories,
            "categories": all_categories,
            "channels": channels,
            "notification_rules": notification_rules,
            "tab": request.query_params.get("tab"),
        },
    )


@router.get("/admin/users", response_class=HTMLResponse, response_model=None)
async def admin_users_page(
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return RedirectResponse("/login", status_code=302)
    if user.role != "admin":
        return RedirectResponse("/", status_code=302)

    result = await db.execute(select(User).order_by(User.created_at))
    users = result.scalars().all()

    return templates.TemplateResponse(
        "admin/users.html", {"request": request, "user": user, "users": users}
    )


# ---------------------------------------------------------------------------
# HTMX partial routes
# ---------------------------------------------------------------------------

PER_PAGE = 20


async def _fetch_articles(
    db: AsyncSession,
    *,
    q: str | None = None,
    platform: str | None = None,
    is_bookmarked: bool = False,
    category_slug: str | None = None,
    tag_name: str | None = None,
    page: int = 1,
) -> tuple[list[Article], bool]:
    """Fetch articles with filters. Returns (articles, has_next_page)."""
    query = (
        select(Article)
        .options(selectinload(Article.tags), selectinload(Article.category))
        .order_by(Article.collected_at.desc())
    )

    if q:
        query = query.where(Article.title.ilike(f"%{q}%") | Article.content.ilike(f"%{q}%"))
    if platform:
        query = query.where(Article.source_platform == platform)
    if is_bookmarked:
        query = query.where(Article.is_bookmarked.is_(True))
    if category_slug:
        query = query.join(Category, Article.category_id == Category.id).where(
            Category.slug == category_slug
        )
    if tag_name:
        query = query.join(Article.tags).where(Tag.name == tag_name)

    query = query.offset((page - 1) * PER_PAGE).limit(PER_PAGE + 1)
    result = await db.execute(query)
    articles = list(result.scalars().unique().all())

    has_next = len(articles) > PER_PAGE
    if has_next:
        articles = articles[:PER_PAGE]

    return articles, has_next


@router.get("/htmx/articles", response_class=HTMLResponse, response_model=None)
async def htmx_articles(
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return Response(status_code=401)

    params = request.query_params
    q = params.get("q") or None
    platform = params.get("platform") or None
    is_bookmarked = params.get("is_bookmarked") == "true"
    category = params.get("category") or None
    tag = params.get("tag") or None
    page = int(params.get("page", "1"))

    articles, has_next = await _fetch_articles(
        db,
        q=q,
        platform=platform,
        is_bookmarked=is_bookmarked,
        category_slug=category,
        tag_name=tag,
        page=page,
    )

    return templates.TemplateResponse(
        "partials/article_list.html",
        {
            "request": request,
            "articles": articles,
            "has_next": has_next,
            "next_page": page + 1,
            "q": q,
            "platform": platform,
            "is_bookmarked": is_bookmarked,
            "category": category,
            "tag": tag,
        },
    )


@router.post("/htmx/toggle-bookmark/{article_id}", response_class=HTMLResponse, response_model=None)
async def htmx_toggle_bookmark(
    article_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return Response(status_code=401)
    try:
        aid = uuid.UUID(article_id)
    except ValueError:
        return Response(status_code=400)

    result = await db.execute(
        select(Article)
        .options(selectinload(Article.tags), selectinload(Article.category))
        .where(Article.id == aid)
    )
    article = result.scalar_one_or_none()
    if not article:
        return Response(status_code=404)

    article.is_bookmarked = not article.is_bookmarked
    await db.flush()

    return templates.TemplateResponse(
        "partials/article_card.html", {"request": request, "article": article}
    )


@router.post("/htmx/toggle-read/{article_id}", response_class=HTMLResponse, response_model=None)
async def htmx_toggle_read(
    article_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return Response(status_code=401)
    try:
        aid = uuid.UUID(article_id)
    except ValueError:
        return Response(status_code=400)

    result = await db.execute(
        select(Article)
        .options(selectinload(Article.tags), selectinload(Article.category))
        .where(Article.id == aid)
    )
    article = result.scalar_one_or_none()
    if not article:
        return Response(status_code=404)

    article.is_read = not article.is_read
    await db.flush()

    return templates.TemplateResponse(
        "partials/article_card.html", {"request": request, "article": article}
    )


@router.post("/htmx/sources", response_class=HTMLResponse, response_model=None)
async def htmx_add_source(
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user or user.role not in ("admin", "editor"):
        return Response(status_code=403)

    form = await request.form()
    name = form.get("name", "")
    platform = form.get("platform", "rss")
    url = form.get("url", "")
    interval = int(form.get("collect_interval_min", "30"))

    config = {"url": url}
    language = form.get("language", "").strip()
    if language and platform == "newspaper":
        config["language"] = language
    category_id = form.get("category_id", "").strip()

    from cyberfeed.services.source_service import SourceService

    svc = SourceService()
    source = await svc.create(db, name, platform, config, interval)
    if not source:
        import json as _json

        msg = "A source with this URL already exists"
        return Response(
            status_code=200,
            content="",
            headers={
                "HX-Trigger": _json.dumps(
                    {"showToast": {"message": msg, "type": "error"}}
                )
            },
        )

    if category_id:
        from cyberfeed.models.source import source_categories

        await db.execute(
            source_categories.insert().values(
                source_id=source.id, category_id=uuid.UUID(category_id)
            )
        )

    return Response(status_code=200)


@router.post("/htmx/sources/probe", response_model=None)
async def htmx_probe_source(
    request: Request,
    user: User | None = Depends(_get_optional_user),
):
    if not user or user.role not in ("admin", "editor"):
        return Response(status_code=403)

    form = await request.form()
    url = (form.get("url", "") or "").strip()
    platform = form.get("platform", "rss")
    if not url:
        return Response(
            content=(
                '<div class="alert alert-error text-sm">'
                "<span>Please enter a URL first.</span></div>"
            ),
            media_type="text/html",
        )

    from cyberfeed.services.source_service import SourceService

    svc = SourceService()
    result = await svc.probe_url(url)

    def _alert(level: str, msg: str) -> str:
        return f'<div class="alert alert-{level} text-sm"><span>{msg}</span></div>'

    if not result["reachable"]:
        err = result["error"]
        html = _alert("error", f"URL not reachable: {err}")
    elif result["is_rss"] and platform == "newspaper":
        html = _alert(
            "warning",
            'This looks like an RSS feed. Consider using "RSS / Atom" platform.',
        )
    elif not result["is_rss"] and platform == "rss":
        html = _alert(
            "warning",
            'This does not look like an RSS feed. Consider "Newspaper" platform.',
        )
    else:
        html = _alert("success", "URL is reachable and format looks correct.")

    return Response(content=html, media_type="text/html")


@router.post("/htmx/sources/{source_id}/collect", response_model=None)
async def htmx_collect_source(
    source_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user or user.role not in ("admin", "editor"):
        return Response(status_code=403)

    try:
        sid = uuid.UUID(source_id)
    except ValueError:
        return Response(status_code=400)

    from cyberfeed.models.source import Source

    result = await db.execute(
        select(Source).options(selectinload(Source.categories)).where(Source.id == sid)
    )
    source = result.scalar_one_or_none()
    if not source:
        return Response(status_code=404)

    import json

    from cyberfeed.services.collector_service import CollectorService

    svc = CollectorService()
    try:
        collect_result = await svc.collect_source(db, source)
    except Exception:
        logger.exception("Collection failed", source_id=source_id)
        msg = "Collection failed — check server logs"
        return Response(
            status_code=200,
            content="",
            headers={
                "HX-Trigger": json.dumps(
                    {"showToast": {"message": msg, "type": "error"}}
                )
            },
        )

    msg = f"Collected {collect_result.new_count} new articles"
    if collect_result.errors:
        msg += f" ({len(collect_result.errors)} errors)"
    toast_type = "success" if not collect_result.errors else "warning"

    return Response(
        status_code=200,
        content="",
        headers={"HX-Trigger": json.dumps({"showToast": {"message": msg, "type": toast_type}})},
    )


@router.patch("/htmx/admin/users/{user_id}/role", response_model=None)
async def htmx_update_user_role(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user or user.role != "admin":
        return Response(status_code=403)

    form = await request.form()
    new_role = form.get("role")
    if new_role not in ("admin", "editor", "reader"):
        return Response(status_code=400)

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return Response(status_code=400)

    if uid == user.id:
        return Response(status_code=400)

    result = await db.execute(select(User).where(User.id == uid))
    target_user = result.scalar_one_or_none()
    if not target_user:
        return Response(status_code=404)

    target_user.role = new_role
    await db.flush()

    return Response(status_code=200)


@router.delete("/htmx/admin/users/{user_id}", response_model=None)
async def htmx_delete_user(
    user_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user or user.role != "admin":
        return Response(status_code=403)

    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        return Response(status_code=400)

    if uid == user.id:
        return Response(status_code=400)

    result = await db.execute(select(User).where(User.id == uid))
    target_user = result.scalar_one_or_none()
    if not target_user:
        return Response(status_code=404)

    await db.delete(target_user)
    await db.flush()

    return Response(status_code=200, content="")


@router.delete("/htmx/sources/{source_id}", response_model=None)
async def htmx_delete_source(
    source_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user or user.role not in ("admin", "editor"):
        return Response(status_code=403)

    try:
        sid = uuid.UUID(source_id)
    except ValueError:
        return Response(status_code=400)

    from cyberfeed.services.source_service import SourceService

    svc = SourceService()
    deleted = await svc.delete(db, sid)
    if not deleted:
        return Response(status_code=404)

    import json

    return Response(
        status_code=200,
        content="",
        headers={
            "HX-Trigger": json.dumps(
                {"showToast": {"message": "Source deleted", "type": "success"}}
            )
        },
    )


@router.post("/htmx/notifications", response_model=None)
async def htmx_add_notification_rule(
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return Response(status_code=403)

    form = await request.form()
    channel = form.get("channel", "")
    destination = form.get("destination", "").strip()
    keywords_raw = form.get("keywords", "").strip()
    keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()] if keywords_raw else []

    if not channel or not destination:
        return Response(status_code=400)

    from cyberfeed.services.notification_service import NotificationService

    svc = NotificationService()
    await svc.create_rule(db, user.id, channel, destination, keywords=keywords)

    import json

    return Response(
        status_code=200,
        content="",
        headers={
            "HX-Trigger": json.dumps(
                {"showToast": {"message": "Notification rule added", "type": "success"}}
            )
        },
    )


@router.delete("/htmx/notifications/{rule_id}", response_model=None)
async def htmx_delete_notification_rule(
    rule_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user:
        return Response(status_code=403)

    try:
        rid = uuid.UUID(rule_id)
    except ValueError:
        return Response(status_code=400)

    from cyberfeed.services.notification_service import NotificationService

    svc = NotificationService()
    deleted = await svc.delete_rule(db, rid, user.id)
    if not deleted:
        return Response(status_code=404)

    import json

    return Response(
        status_code=200,
        content="",
        headers={
            "HX-Trigger": json.dumps(
                {"showToast": {"message": "Rule deleted", "type": "success"}}
            )
        },
    )


# ---------------------------------------------------------------------------
# Category HTMX routes
# ---------------------------------------------------------------------------


def _slugify(name: str) -> str:
    """Convert a category name to a URL-safe slug."""
    import re
    import unicodedata

    slug = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", slug).strip().lower()
    return re.sub(r"[-\s]+", "-", slug)


@router.post("/htmx/categories", response_model=None)
async def htmx_add_category(
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user or user.role not in ("admin", "editor"):
        return Response(status_code=403)

    form = await request.form()
    name = (form.get("name", "") or "").strip()
    color = (form.get("color", "#6b7280") or "#6b7280").strip()
    sort_order = int(form.get("sort_order", "0") or "0")

    if not name:
        return Response(status_code=400)

    slug = _slugify(name)

    # Check uniqueness
    existing = await db.execute(
        select(Category).where((Category.slug == slug) | (Category.name == name))
    )
    if existing.scalar_one_or_none():
        import json

        return Response(
            status_code=200,
            content="",
            headers={
                "HX-Trigger": json.dumps(
                    {"showToast": {"message": "Category already exists", "type": "error"}}
                )
            },
        )

    cat = Category(name=name, slug=slug, color=color, sort_order=sort_order)
    db.add(cat)
    await db.flush()

    import json

    return Response(
        status_code=200,
        content="",
        headers={
            "HX-Trigger": json.dumps(
                {"showToast": {"message": f"Category '{name}' added", "type": "success"}}
            )
        },
    )


@router.delete("/htmx/categories/{category_id}", response_model=None)
async def htmx_delete_category(
    category_id: str,
    request: Request,
    db: AsyncSession = Depends(_get_db),
    user: User | None = Depends(_get_optional_user),
):
    if not user or user.role not in ("admin", "editor"):
        return Response(status_code=403)

    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        return Response(status_code=400)

    result = await db.execute(select(Category).where(Category.id == cid))
    cat = result.scalar_one_or_none()
    if not cat:
        return Response(status_code=404)

    await db.delete(cat)
    await db.flush()

    import json

    return Response(
        status_code=200,
        content="",
        headers={
            "HX-Trigger": json.dumps(
                {"showToast": {"message": "Category deleted", "type": "success"}}
            )
        },
    )
