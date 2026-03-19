# CyberFeed

> Self-hosted news aggregator with optional AI summarization, Telegram/email notifications, and a mobile-friendly web UI.

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688)](https://fastapi.tiangolo.com)
[![Tests](https://img.shields.io/badge/tests-26%20passing-brightgreen)](tests/)
[![Ruff](https://img.shields.io/badge/linting-ruff-261230)](https://docs.astral.sh/ruff/)

---

## What is CyberFeed?

CyberFeed aggregates articles from **RSS feeds**, **news websites**, and **X.com** into a single searchable, categorized feed. Everything runs locally — no cloud required.

**Key features:**

- **Multiple sources** — RSS/Atom, full-article newspaper extraction, X.com (via RSS bridge or API v2)
- **Responsive web UI** — mobile-first, dark mode, PWA (installable on phone)
- **Search & filter** — full-text search, filter by category, tag, platform, bookmarks
- **Infinite scroll** — HTMX-powered, no page reloads
- **Categories & tags** — organize articles; tags auto-extracted from feeds
- **Optional AI summaries** — LiteLLM (OpenAI, Anthropic, Ollama, etc.) with extractive fallback
- **Notifications** — Telegram bot and/or email; keyword/category/platform rules
- **OPML import/export** — migrate from any RSS reader
- **Multi-user** — roles: `admin`, `editor`, `reader`; JWT + httpOnly cookie auth
- **REST API** — full JSON API with Bearer token auth; Swagger UI in debug mode

---

## Quick Start

### Docker (recommended)

**Prerequisites:** Docker, Docker Compose

```bash
# 1. Clone and configure
git clone https://github.com/your-org/cyberfeed.git
cd cyberfeed
cp .env.example .env

# 2. Set a strong secret key (required)
#    macOS/Linux:
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
#    Or edit .env manually

# 3. Start
docker compose up -d

# 4. Open in browser
open http://localhost:8000
```

The first user you register becomes **admin**.

---

### Manual (development)

**Prerequisites:** Python 3.12+, [`uv`](https://docs.astral.sh/uv/getting-started/installation/)

```bash
# 1. Install dependencies
uv sync --all-extras

# 2. Configure
cp .env.example .env
# Edit .env — set SECRET_KEY to a random string ≥ 32 characters

# 3. Run database migrations
uv run alembic upgrade head

# 4. (Optional) Seed demo RSS sources
uv run python scripts/seed_sources.py

# 5. Start the dev server
uv run uvicorn cyberfeed.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000) — register your first user (becomes admin).

---

## Configuration

All settings are loaded from `.env`. Copy `.env.example` to get started.

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | *(required)* | Random string ≥ 32 chars. Used for JWT signing and encrypting stored credentials. |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/cyberfeed.db` | SQLite database path. |
| `REGISTRATION_OPEN` | `true` | Allow public registration. Set `false` after creating accounts. |
| `DEBUG` | `false` | Enable Swagger UI at `/api/docs` and verbose logging. |
| `ALLOWED_ORIGINS` | `http://localhost:8000` | Comma-separated CORS origins. |
| `LLM_ENABLED` | `false` | Enable LLM summarization. |
| `LLM_MODEL` | `gpt-4o-mini` | Any [LiteLLM-supported model](https://docs.litellm.ai/docs/providers). |
| `LLM_API_KEY` | *(empty)* | API key for your LLM provider. |
| `LLM_API_BASE` | *(empty)* | Custom base URL (e.g., `http://localhost:11434` for Ollama). |
| `TELEGRAM_ENABLED` | `false` | Enable Telegram notifications. |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Bot token from [@BotFather](https://t.me/botfather). |
| `EMAIL_ENABLED` | `false` | Enable email notifications. |
| `SMTP_HOST` | *(empty)* | SMTP server hostname. |
| `SMTP_PORT` | `587` | SMTP port (587 = STARTTLS, 465 = SSL). |
| `SMTP_USERNAME` | *(empty)* | SMTP authentication username. |
| `SMTP_PASSWORD` | *(empty)* | SMTP authentication password. |
| `SMTP_FROM` | *(empty)* | Sender address (e.g., `cyberfeed@example.com`). |
| `SMTP_USE_TLS` | `true` | Use STARTTLS. |
| `COLLECT_DEFAULT_INTERVAL_MIN` | `30` | Default collection interval per source (minutes). |

See [docs/configuration.md](docs/configuration.md) for the full reference, including LiteLLM provider examples and Telegram/email setup guides.

---

## Usage

### 1. Add sources

Go to **Settings → Sources** and click **Add Source**. Choose a platform:

| Platform | What it collects | Config needed |
|----------|-----------------|---------------|
| **RSS** | Any RSS/Atom feed | Feed URL |
| **Newspaper** | Full articles from a news website | Site URL |
| **X.com** | Twitter/X posts | RSSHub URL *or* API Bearer Token |

Or import all your existing feeds at once via **Import OPML**.

### 2. Browse the feed

The main feed shows articles in reverse-chronological order. Use the:

- **Left sidebar** — filter by category (admin/editor can create categories under Settings)
- **Tag cloud** — click any tag to filter
- **Search bar** — full-text search across titles and content
- **Platform filter** — show only RSS, Newspaper, or X.com articles
- **Bookmarks toggle** — show only bookmarked articles

### 3. Article actions

On any article card:
- ☆ / ★ — toggle bookmark
- **Mark read** — mark as read (read articles are de-emphasized)
- Click the title — open full article view with summary, tags, source link

### 4. Set up notifications

Go to **Settings → Notifications**. Create a rule:

- **Channel** — Telegram or Email
- **Destination** — your Telegram chat ID or email address
- **Keywords** — articles containing any of these words trigger a notification (leave empty = all articles)
- **Platform filter** — restrict to specific platforms

Use the **Test** button to verify your channel is configured correctly.

### 5. AI summaries

If `LLM_ENABLED=true`, new articles are summarized automatically (every 5 minutes). You can also summarize an article on demand from its detail page.

If LLM is disabled or unavailable, CyberFeed falls back to extractive summarization (first 3 sentences).

---

## API

CyberFeed exposes a full REST API at `/api`. Authentication uses **Bearer tokens** (obtain via `POST /api/auth/login`).

**Swagger UI** is available at `http://localhost:8000/api/docs` when `DEBUG=true`.

Key endpoints:

```
POST /api/auth/register         Register new user
POST /api/auth/login            Login → get access + refresh tokens
POST /api/auth/refresh          Rotate refresh token

GET  /api/articles              List/search articles
GET  /api/articles/{id}         Article detail
POST /api/articles/{id}/summarize  Trigger summarization

GET  /api/sources               List sources
POST /api/sources               Add source
POST /api/sources/{id}/collect  Trigger immediate collection
POST /api/sources/import-opml   Import OPML file
GET  /api/sources/export-opml   Export OPML file

GET  /api/categories            List categories
GET  /api/tags/popular          Popular tags

GET  /api/notifications/channels    Available channels
POST /api/notifications/rules       Create notification rule
POST /api/notifications/test        Send test notification

GET  /api/health                Health check
```

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                   Web Browser                   │
│         Jinja2 + HTMX + Tailwind/DaisyUI        │
└────────────────────┬────────────────────────────┘
                     │ HTTP
┌────────────────────▼────────────────────────────┐
│                   FastAPI App                   │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │  web/routes  │  │      api/ (REST JSON)     │ │
│  │  (HTML+HTMX) │  │  auth, articles, sources, │ │
│  └──────┬───────┘  │  categories, tags, notifs │ │
│         │          └─────────────┬────────────┘ │
│  ┌──────▼──────────────────────▼────────────┐  │
│  │              services/                    │  │
│  │  article · source · auth · summary · notif│  │
│  └──────────────────┬────────────────────────┘  │
│  ┌────────┐  ┌──────▼───────┐  ┌─────────────┐  │
│  │schedule│  │  SQLAlchemy  │  │  collectors/ │  │
│  │  jobs  │  │   SQLite DB  │  │  rss · paper │  │
│  └───┬────┘  └──────────────┘  │  · x_com     │  │
│      │                         └─────────────┘  │
│  ┌───▼──────────────────────────────────────┐   │
│  │  summarizer/        notifiers/            │   │
│  │  litellm · extract  telegram · email      │   │
│  └───────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

**Source layout:** `src/cyberfeed/` (PEP 621)

| Package | Responsibility |
|---------|---------------|
| `models/` | SQLAlchemy ORM (Article, Source, User, Category, Tag, NotificationRule) |
| `schemas/` | Pydantic request/response models |
| `services/` | Business logic — no HTTP, no DB sessions leaked |
| `api/` | REST JSON routes (`/api/*`) |
| `web/` | Server-rendered HTML routes + Jinja2 templates |
| `collectors/` | Pluggable feed collectors (`AbstractCollector`) |
| `summarizer/` | LLM + extractive summarization |
| `notifiers/` | Pluggable notification channels (`AbstractNotifier`) |
| `scheduler/` | APScheduler background jobs |
| `core/` | Security, middleware, exceptions, logging |

---

## Development

### Commands

```bash
# Install (including dev extras)
uv sync --all-extras

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Database migration (after model changes)
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head

# Dev server with auto-reload
uv run uvicorn cyberfeed.main:app --reload
```

### Extending the system

- **Add a collector** — see [docs/development.md#adding-a-collector](docs/development.md#adding-a-collector)
- **Add a notifier** — see [docs/development.md#adding-a-notifier](docs/development.md#adding-a-notifier)

---

## License

MIT
