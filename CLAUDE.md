# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CyberFeed is a Python-based information collecting system that aggregates news from X.com, RSS feeds, and newspapers. It features optional LLM summarization (via LiteLLM), Telegram/email notifications, and a responsive web UI.

## Commands

```bash
# Install dependencies
uv sync --all-extras

# Run dev server
uv run uvicorn cyberfeed.main:app --reload

# Run tests
uv run pytest tests/ -v

# Lint & format
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Database migrations
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

# Docker
docker compose up
```

## Architecture

- **Stack:** FastAPI + SQLAlchemy 2.0 async + SQLite + Jinja2/HTMX/Tailwind/DaisyUI
- **Package manager:** uv
- **Source layout:** `src/cyberfeed/` (PEP 621 src layout)

### Key Layers

- `models/` — SQLAlchemy ORM models (Base in `models/base.py`)
- `schemas/` — Pydantic request/response schemas
- `services/` — Business logic (no HTTP concerns)
- `api/` — REST API routes (JSON), uses `api/deps.py` for shared dependencies
- `web/` — Server-rendered HTML routes (Jinja2 + HTMX), cookie-based auth
- `collectors/` — Pluggable feed collectors implementing `AbstractCollector`
- `summarizer/` — LLM summarization with extractive fallback
- `notifiers/` — Pluggable notification channels implementing `AbstractNotifier`
- `core/` — Cross-cutting: security, middleware, exceptions, logging
- `scheduler/` — APScheduler background jobs

### Plugin Pattern

Collectors, summarizers, and notifiers follow an abstract base class pattern. New implementations register via `CollectorRegistry`. Each collector defines a `platform_key` and `get_config_schema()` for dynamic form rendering.

### Auth

Multi-user with roles: admin > editor > reader. JWT access tokens (15min) + refresh tokens (7d). Web UI uses httpOnly cookies; API uses Bearer tokens.

### Config

All settings via pydantic-settings (`config.py`), loaded from `.env`. Sensitive fields in DB encrypted with Fernet (derived from SECRET_KEY).

## Implementation Status

All 8 phases complete:

| Phase | Status | Notes |
|-------|--------|-------|
| Foundation | ✅ | FastAPI app, DB engine, Alembic, config, logging, middleware |
| Collectors | ✅ | RSS, Newspaper4k, X.com (RSS bridge + API v2); `CollectorRegistry` |
| API + Auth | ✅ | 27 REST endpoints; JWT + cookie auth; RBAC; OPML import/export |
| Web Frontend | ✅ | Jinja2 + HTMX + DaisyUI; dark mode; PWA (manifest + sw.js) |
| Summarization | ✅ | LiteLLM + extractive fallback; circuit breaker (5 failures → 10min cooldown) |
| Notifications | ✅ | Telegram + email notifiers; keyword/category/platform rule matching |
| Extras | ✅ | PWA, dark mode toggle, OPML import/export |
| Hardening | ✅ | 26 passing tests; ruff lint + format clean |

## Key Files

- `src/cyberfeed/main.py` — app factory; mounts API + web routers
- `src/cyberfeed/config.py` — all settings (pydantic-settings, `.env`)
- `src/cyberfeed/api/__init__.py` — `create_api_router()` combining all sub-routers
- `src/cyberfeed/web/routes.py` — page + HTMX partial routes with cookie auth
- `src/cyberfeed/collectors/registry.py` — `CollectorRegistry`; `register_all_collectors()`
- `src/cyberfeed/scheduler/jobs.py` — collect / summarize / notify background jobs
- `src/cyberfeed/services/summary_service.py` — LLM circuit breaker logic
- `src/cyberfeed/services/notification_service.py` — rule matching + dispatch

## Notes

- Login endpoint (`POST /api/auth/login`) accepts **JSON** body `{"username": ..., "password": ...}`, not form-encoded.
- API tests use in-memory SQLite; the `_init_app_db` autouse fixture creates tables before each test.
- The web UI needs `SECRET_KEY` ≥ 32 chars set in `.env` to start.
- `apscheduler>=3.10` is required (4.x is alpha-only; do not upgrade).
