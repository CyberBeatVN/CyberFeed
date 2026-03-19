# CyberFeed — Development Guide

## Setup

```bash
# Install all dependencies including dev extras
uv sync --all-extras

# Run database migrations
uv run alembic upgrade head

# (Optional) Seed demo RSS sources
uv run python scripts/seed_sources.py

# Start dev server with auto-reload
uv run uvicorn cyberfeed.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000). The first account you register becomes admin.

---

## Daily Commands

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_api/test_auth.py -v

# Lint (check only)
uv run ruff check src/ tests/

# Format
uv run ruff format src/ tests/

# Lint + auto-fix
uv run ruff check --fix src/ tests/
```

---

## Adding a Collector

Collectors pull articles from external sources. Each collector handles one platform (RSS, newspaper, X.com, etc.).

### 1. Create the collector file

Create `src/cyberfeed/collectors/myplatform.py`:

```python
"""Collector for MyPlatform."""

import structlog
from cyberfeed.collectors.base import AbstractCollector, CollectedArticle
from cyberfeed.collectors.registry import CollectorRegistry

logger = structlog.get_logger()


@CollectorRegistry.register
class MyPlatformCollector(AbstractCollector):
    # Unique key — used in the Source.platform DB column and API responses.
    # Use lowercase, no spaces (e.g., "rss", "newspaper", "x.com", "reddit").
    platform_key = "myplatform"

    async def collect(self, source_config: dict) -> list[CollectedArticle]:
        """
        Fetch articles from the source.

        source_config contains the validated fields defined in get_config_schema().
        This method must not raise exceptions — catch errors, log them, and return
        a partial list (or empty list on total failure).
        """
        url = source_config["url"]
        articles = []

        try:
            # ... fetch and parse articles ...
            articles.append(
                CollectedArticle(
                    title="Article title",
                    url="https://example.com/article",
                    content="Full article text...",
                    source_name=source_config.get("source_name", url),
                    source_platform=self.platform_key,
                    # Optional fields:
                    # published_at=datetime(..., tzinfo=UTC),
                    # author="Author Name",
                    # image_url="https://example.com/image.jpg",
                    # tags=["tag1", "tag2"],
                    # metadata={"any": "extra data"},
                )
            )
        except Exception:
            logger.exception("MyPlatform fetch failed", url=url)

        logger.info("MyPlatform collected", url=url, count=len(articles))
        return articles

    async def validate_config(self, config: dict) -> tuple[bool, str]:
        """
        Validate source configuration before saving to the database.
        Called when a user adds or edits a source via the UI or API.
        Returns (is_valid, error_message). Return ("", ) on success.
        """
        url = config.get("url", "")
        if not url:
            return False, "URL is required"
        if not url.startswith(("http://", "https://")):
            return False, "URL must start with http:// or https://"
        return True, ""

    def get_config_schema(self) -> dict:
        """
        Describe the configuration fields for this collector.
        The UI renders a dynamic form based on this schema.

        Supported field types: "string", "integer", "password", "select"
        For "select" type, provide "options": ["opt1", "opt2"]
        For "password" type, the value is Fernet-encrypted at rest.
        """
        return {
            "url": {
                "type": "string",
                "required": True,
                "label": "Source URL",
            },
            "max_entries": {
                "type": "integer",
                "required": False,
                "default": 50,
                "label": "Max entries per fetch",
            },
        }
```

The `@CollectorRegistry.register` decorator registers your collector automatically when the module is imported.

### 2. Register the import

Add your module to `register_all_collectors()` in `src/cyberfeed/collectors/registry.py`:

```python
def register_all_collectors() -> None:
    import cyberfeed.collectors.newspaper
    import cyberfeed.collectors.rss
    import cyberfeed.collectors.x_com
    import cyberfeed.collectors.myplatform  # add this line
```

### 3. Write tests

Create `tests/test_collectors/test_myplatform.py`:

```python
"""Tests for MyPlatformCollector."""

import pytest
from cyberfeed.collectors.myplatform import MyPlatformCollector


@pytest.mark.asyncio
async def test_validate_config_requires_url():
    collector = MyPlatformCollector()
    ok, err = await collector.validate_config({})
    assert not ok
    assert "URL" in err


@pytest.mark.asyncio
async def test_collect_returns_articles(respx_mock):
    # Use respx to mock HTTP calls if your collector uses httpx
    import respx
    import httpx

    with respx.mock:
        respx.get("https://example.com/feed").mock(
            return_value=httpx.Response(200, text="<rss>...</rss>")
        )
        collector = MyPlatformCollector()
        articles = await collector.collect({"url": "https://example.com/feed"})
        assert isinstance(articles, list)
```

### CollectedArticle fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | str | yes | Article headline |
| `url` | str | yes | Canonical article URL (used for deduplication) |
| `content` | str | yes | Full text content (HTML or plain text; sanitized before storage) |
| `source_name` | str | yes | Human-readable source name shown in the UI |
| `source_platform` | str | yes | Must match `platform_key` |
| `published_at` | datetime\|None | no | Publication time (timezone-aware) |
| `author` | str\|None | no | Author name |
| `image_url` | str\|None | no | Featured image URL |
| `tags` | list[str] | no | Tags/keywords (auto-created in DB) |
| `metadata` | dict | no | Platform-specific data stored as JSON |

---

## Adding a Notifier

Notifiers send notifications through a specific channel (Telegram, email, Slack, etc.).

### 1. Create the notifier file

Create `src/cyberfeed/notifiers/mychannel.py`:

```python
"""MyChannel notifier."""

import structlog
from cyberfeed.notifiers.base import AbstractNotifier, NotificationPayload

logger = structlog.get_logger()


class MyChannelNotifier(AbstractNotifier):

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def send(self, recipient: str, payload: NotificationPayload) -> bool:
        """
        Send a notification to `recipient`.

        recipient: channel-specific identifier (chat ID, email address, webhook URL, etc.)
        payload:   NotificationPayload with subject, body, html_body, article_url, article_title

        Returns True on success. Must not raise — catch all exceptions and return False.
        """
        try:
            # ... send the notification ...
            logger.info("MyChannel notification sent", recipient=recipient)
            return True
        except Exception:
            logger.exception("MyChannel send failed", recipient=recipient)
            return False

    async def validate_recipient(self, recipient: str) -> tuple[bool, str]:
        """
        Validate the recipient identifier before saving a notification rule.
        Returns (is_valid, error_message).
        """
        if not recipient:
            return False, "Recipient is required"
        # Add format checks here (e.g., regex for email, numeric for Telegram)
        return True, ""
```

### 2. Wire it into NotificationService

Open `src/cyberfeed/services/notification_service.py` and add your notifier to `__init__`:

```python
from cyberfeed.notifiers.mychannel import MyChannelNotifier

class NotificationService:
    def __init__(self, settings: Settings):
        self._notifiers: dict[str, AbstractNotifier] = {}

        if settings.TELEGRAM_ENABLED and settings.TELEGRAM_BOT_TOKEN:
            self._notifiers["telegram"] = TelegramNotifier(settings.TELEGRAM_BOT_TOKEN)

        if settings.EMAIL_ENABLED and settings.SMTP_HOST:
            self._notifiers["email"] = EmailNotifier(...)

        # Add your notifier:
        if settings.MY_CHANNEL_ENABLED and settings.MY_CHANNEL_API_KEY:
            self._notifiers["mychannel"] = MyChannelNotifier(settings.MY_CHANNEL_API_KEY)
```

### 3. Add settings

Add new fields to `src/cyberfeed/config.py`:

```python
MY_CHANNEL_ENABLED: bool = False
MY_CHANNEL_API_KEY: str = ""
```

And add them to `.env.example`:

```env
# === MyChannel (optional) ===
MY_CHANNEL_ENABLED=false
MY_CHANNEL_API_KEY=
```

### 4. Expose the channel in the API

The `GET /api/notifications/channels` endpoint lists enabled channels. Update `src/cyberfeed/api/notifications.py`:

```python
@router.get("/channels")
async def list_channels(settings: Settings = Depends(get_settings)):
    channels = []
    if settings.TELEGRAM_ENABLED:
        channels.append("telegram")
    if settings.EMAIL_ENABLED:
        channels.append("email")
    if settings.MY_CHANNEL_ENABLED:
        channels.append("mychannel")
    return {"channels": channels}
```

### NotificationPayload fields

| Field | Type | Description |
|-------|------|-------------|
| `subject` | str | Notification title / email subject |
| `body` | str | Plain text content |
| `html_body` | str\|None | HTML content (for email) |
| `article_url` | str\|None | Link to the original article |
| `article_title` | str\|None | Article headline |

---

## Database Migrations

CyberFeed uses [Alembic](https://alembic.sqlalchemy.org/) for schema migrations.

### After changing a model

```bash
# 1. Generate a migration (autogenerate detects model changes)
uv run alembic revision --autogenerate -m "add myfield to articles"

# 2. Review the generated file in alembic/versions/
# Always check autogenerated migrations before applying them.

# 3. Apply to the database
uv run alembic upgrade head
```

### Common Alembic commands

```bash
# Show current migration
uv run alembic current

# Show migration history
uv run alembic history

# Roll back one migration
uv run alembic downgrade -1

# Roll back to a specific revision
uv run alembic downgrade <revision_id>
```

### Adding a new model

1. Create the model file in `src/cyberfeed/models/`
2. Import it in `src/cyberfeed/models/__init__.py` so Alembic discovers it
3. Run `uv run alembic revision --autogenerate -m "add mymodel"`
4. Apply with `uv run alembic upgrade head`

---

## Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_api/test_auth.py -v

# Run a specific test function
uv run pytest tests/test_api/test_auth.py::test_login_success -v

# Stop on first failure
uv run pytest tests/ -x

# Show print output
uv run pytest tests/ -s
```

### Test structure

```
tests/
├── conftest.py            # shared fixtures (db, client, auth_client)
├── test_api/
│   ├── test_auth.py       # auth endpoints
│   ├── test_articles.py   # articles CRUD
│   └── test_sources.py    # source management
├── test_services/
│   ├── test_article_service.py
│   ├── test_auth_service.py
│   ├── test_collector_service.py
│   └── test_summary_service.py
├── test_collectors/
│   ├── test_rss.py
│   └── test_newspaper.py
└── test_notifiers/
    ├── test_telegram.py
    └── test_email.py
```

### Key fixtures (from `conftest.py`)

| Fixture | Description |
|---------|-------------|
| `client` | ASGI test client using an in-memory SQLite database |
| `auth_client` | Same client, pre-authenticated as admin (`testadmin` / `testpassword123`) |
| `db_session` | Raw SQLAlchemy session connected to an isolated in-memory DB |
| `_init_app_db` | Autouse — creates all tables before each test, drops them after |

### Writing async tests

All tests are async. Mark them with `@pytest.mark.asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_something(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
```

The `asyncio_mode = "auto"` setting in `pyproject.toml` makes `@pytest.mark.asyncio` the default, so you can also omit the decorator.

### Mocking HTTP in collectors

Use [respx](https://lundberg.github.io/respx/) to mock `httpx` calls:

```python
import pytest
import respx
import httpx

@pytest.mark.asyncio
async def test_collector_with_mock():
    with respx.mock:
        respx.get("https://example.com/feed").mock(
            return_value=httpx.Response(200, content=b"<rss>...</rss>")
        )
        # ... test your collector ...
```

---

## Lint & Format

CyberFeed uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting.

```bash
# Check for lint errors
uv run ruff check src/ tests/

# Auto-fix lint errors
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/

# Check formatting without applying
uv run ruff format --check src/ tests/
```

### Ruff configuration

Configured in `pyproject.toml`:

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "W", "I", "S", "B", "UP", "N", "SIM", "RUF"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "S105", "S106", "S107"]   # allow assert + hardcoded passwords in tests
"src/cyberfeed/api/**" = ["B008"]                # FastAPI Depends() in default args
"src/cyberfeed/web/**" = ["B008"]                # same for web routes
```

Notable rule sets:
- `S` (bandit): security checks — flags hardcoded passwords, shell injection, etc.
- `B` (bugbear): common pitfalls
- `UP` (pyupgrade): modernizes Python syntax
- `I` (isort): import ordering

---

## Project Layout

```
src/cyberfeed/
├── main.py            # FastAPI app factory + lifespan
├── config.py          # pydantic-settings (all env vars)
├── database.py        # SQLAlchemy engine + session factory
├── models/            # SQLAlchemy ORM models
├── schemas/           # Pydantic request/response schemas
├── services/          # Business logic (no HTTP concerns)
├── api/               # REST JSON routes (/api/*)
├── web/               # Server-rendered HTML + Jinja2 templates
├── collectors/        # Pluggable feed collectors
├── summarizer/        # LLM + extractive summarization
├── notifiers/         # Pluggable notification channels
├── core/              # Security, middleware, exceptions, logging
└── scheduler/         # APScheduler background jobs
```

See [CLAUDE.md](../CLAUDE.md) for the full architecture overview and implementation details.
