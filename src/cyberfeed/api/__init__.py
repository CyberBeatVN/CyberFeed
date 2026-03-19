"""API router combining all sub-routers."""

from fastapi import APIRouter

from cyberfeed.api.articles import router as articles_router
from cyberfeed.api.auth import router as auth_router
from cyberfeed.api.categories import router as categories_router
from cyberfeed.api.notifications import router as notifications_router
from cyberfeed.api.sources import router as sources_router
from cyberfeed.api.tags import router as tags_router
from cyberfeed.api.users import router as users_router


def create_api_router() -> APIRouter:
    api_router = APIRouter()
    api_router.include_router(auth_router)
    api_router.include_router(users_router)
    api_router.include_router(articles_router)
    api_router.include_router(sources_router)
    api_router.include_router(categories_router)
    api_router.include_router(tags_router)
    api_router.include_router(notifications_router)
    return api_router
