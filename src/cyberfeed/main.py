"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from cyberfeed.api import create_api_router
from cyberfeed.collectors.registry import register_all_collectors
from cyberfeed.config import get_settings
from cyberfeed.core.exceptions import register_exception_handlers
from cyberfeed.core.logging import setup_logging
from cyberfeed.core.middleware import (
    add_cors_middleware,
    add_rate_limit_middleware,
    add_request_id_middleware,
    add_security_headers_middleware,
)
from cyberfeed.database import init_database
from cyberfeed.scheduler.jobs import setup_scheduler
from cyberfeed.web.routes import router as web_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(debug=settings.DEBUG)

    # Ensure data directory exists for SQLite
    if "sqlite" in settings.DATABASE_URL:
        db_path = settings.DATABASE_URL.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    # Register all collector plugins
    register_all_collectors()

    await init_database()

    # Start background scheduler
    scheduler = setup_scheduler()
    scheduler.start()

    await logger.ainfo("CyberFeed started", version=settings.APP_VERSION)
    yield

    scheduler.shutdown(wait=False)
    await logger.ainfo("CyberFeed shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        lifespan=lifespan,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url=None,
    )

    # Middleware (order matters — outermost first)
    add_security_headers_middleware(app)
    add_rate_limit_middleware(app)
    add_cors_middleware(app)
    add_request_id_middleware(app)

    # Exception handlers
    register_exception_handlers(app)

    # API routes
    api_router = create_api_router()
    app.include_router(api_router, prefix="/api")

    # Web routes (server-rendered pages + HTMX)
    app.include_router(web_router)

    # Health check
    @app.get("/api/health")
    async def health_check():
        return {"status": "ok", "version": settings.APP_VERSION}

    # Mount static files
    static_dir = Path(__file__).parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


app = create_app()
