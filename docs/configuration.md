# CyberFeed — Configuration Reference

All settings are loaded from your `.env` file via `pydantic-settings`. Copy `.env.example` to get started:

```bash
cp .env.example .env
```

---

## Required Settings

### `SECRET_KEY`

**Type:** string | **Required:** yes

A random string used for:
- Signing JWT access and refresh tokens
- Deriving the Fernet encryption key for sensitive fields stored in the database (source API keys, notification destinations)

**Requirements:** minimum 32 characters.

```bash
# Generate a secure key on Linux/macOS:
echo "SECRET_KEY=$(openssl rand -hex 32)" >> .env
```

> **Warning:** Changing `SECRET_KEY` after the application has run will invalidate all existing sessions and make encrypted database fields unreadable. Do not rotate this key without a migration plan.

---

## Database

### `DATABASE_URL`

**Type:** string | **Default:** `sqlite+aiosqlite:///./data/cyberfeed.db`

SQLAlchemy async database URL. CyberFeed ships with SQLite and no additional setup is needed.

The default path (`./data/cyberfeed.db`) is relative to the working directory. When running with Docker the `data/` directory is mounted as a volume for persistence.

**Examples:**

```env
# SQLite (default) — file at ./data/cyberfeed.db
DATABASE_URL=sqlite+aiosqlite:///./data/cyberfeed.db

# SQLite in-memory (testing only)
DATABASE_URL=sqlite+aiosqlite:///:memory:
```

---

## Auth & Security

### `REGISTRATION_OPEN`

**Type:** boolean | **Default:** `true`

When `true`, anyone can register an account at `/register` or `POST /api/auth/register`.

Set to `false` after creating your accounts to prevent public self-registration. When closed, only an `admin` can create new users via the admin panel.

```env
REGISTRATION_OPEN=false
```

### `DEBUG`

**Type:** boolean | **Default:** `false`

When `true`:
- Enables Swagger UI at `/api/docs`
- Enables SQLAlchemy echo (SQL queries logged)
- Returns detailed error messages in API responses

Do not enable in production.

### `ALLOWED_ORIGINS`

**Type:** comma-separated list | **Default:** `http://localhost:8000`

CORS allowed origins. The web UI makes same-origin requests, so this only matters if you're calling the API from a different domain (e.g., a separate frontend or mobile app).

```env
ALLOWED_ORIGINS=https://feed.example.com,https://app.example.com
```

### JWT Settings

These rarely need changing:

| Variable | Default | Description |
|----------|---------|-------------|
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | Access token lifetime in minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token lifetime in days |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_API` | `60/minute` | General API rate limit per IP |
| `RATE_LIMIT_AUTH` | `10/minute` | Auth endpoint rate limit per IP |

---

## LLM / AI Summarization

CyberFeed uses [LiteLLM](https://docs.litellm.ai/docs/providers) to call any LLM provider. When disabled (the default), CyberFeed falls back to extractive summarization (first 3 sentences of each article).

### `LLM_ENABLED`

**Type:** boolean | **Default:** `false`

Set to `true` to enable AI-powered article summarization. Requires `LLM_MODEL` and (usually) `LLM_API_KEY`.

### `LLM_MODEL`

**Type:** string | **Default:** `gpt-4o-mini`

Any [LiteLLM-supported model](https://docs.litellm.ai/docs/providers). Examples:

| Provider | Model value |
|----------|-------------|
| OpenAI | `gpt-4o-mini`, `gpt-4o`, `gpt-3.5-turbo` |
| Anthropic | `claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-opus-4-6` |
| Ollama (local) | `ollama/llama3.2`, `ollama/mistral` |
| Groq | `groq/llama-3.1-8b-instant` |
| Google | `gemini/gemini-1.5-flash` |

### `LLM_API_KEY`

**Type:** string | **Default:** *(empty)*

API key for your LLM provider. Not needed for Ollama (local).

### `LLM_API_BASE`

**Type:** string | **Default:** *(empty)*

Custom base URL for the LLM API. Required for local models like Ollama:

```env
LLM_API_BASE=http://localhost:11434
```

### `LLM_TIMEOUT`

**Type:** integer (seconds) | **Default:** `30`

Request timeout for LLM API calls. Increase if your model is slow to respond.

### `LLM_MAX_TOKENS`

**Type:** integer | **Default:** `300`

Maximum tokens in the generated summary. 300 tokens ≈ 200–250 words.

### Provider examples

**OpenAI:**
```env
LLM_ENABLED=true
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

**Anthropic:**
```env
LLM_ENABLED=true
LLM_MODEL=claude-haiku-4-5-20251001
LLM_API_KEY=sk-ant-...
```

**Ollama (local, no API key needed):**
```env
LLM_ENABLED=true
LLM_MODEL=ollama/llama3.2
LLM_API_BASE=http://localhost:11434
```

### Circuit breaker

If the LLM API fails 5 times in a row, CyberFeed pauses LLM calls for 10 minutes (circuit breaker). During the cooldown, all articles are summarized with the extractive fallback. After 10 minutes, LLM calls resume automatically.

---

## Telegram Notifications

### Getting a bot token

1. Open Telegram and search for [@BotFather](https://t.me/botfather)
2. Send `/newbot` and follow the prompts (choose a name and username)
3. BotFather sends you a token: `123456789:ABCdef...`

### Getting your chat ID

1. Start a conversation with your bot (send it any message)
2. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser
3. Find `"chat": {"id": 123456789}` in the response — that number is your chat ID

For group chats, add the bot to the group and send a message; the chat ID will be negative (e.g., `-1001234567890`).

### Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_ENABLED` | `false` | Enable Telegram notifications |
| `TELEGRAM_BOT_TOKEN` | *(empty)* | Bot token from BotFather |

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
```

After enabling, configure notification rules in **Settings → Notifications** and enter your chat ID as the destination.

---

## Email Notifications

### Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_ENABLED` | `false` | Enable email notifications |
| `SMTP_HOST` | *(empty)* | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port (587 = STARTTLS, 465 = SSL) |
| `SMTP_USERNAME` | *(empty)* | SMTP authentication username |
| `SMTP_PASSWORD` | *(empty)* | SMTP authentication password |
| `SMTP_FROM` | *(empty)* | Sender address, e.g. `cyberfeed@example.com` |
| `SMTP_USE_TLS` | `true` | Use STARTTLS (recommended) |

### Provider examples

**Gmail:**
```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your-app-password   # use an App Password, not your login password
SMTP_FROM=you@gmail.com
SMTP_USE_TLS=true
```

> Gmail requires an [App Password](https://myaccount.google.com/apppasswords) when 2-step verification is enabled.

**SendGrid:**
```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USERNAME=apikey
SMTP_PASSWORD=SG.your-api-key
SMTP_FROM=cyberfeed@yourdomain.com
SMTP_USE_TLS=true
```

**Mailgun:**
```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USERNAME=postmaster@yourdomain.mailgun.org
SMTP_PASSWORD=your-mailgun-password
SMTP_FROM=cyberfeed@yourdomain.com
SMTP_USE_TLS=true
```

---

## Scheduler

### `COLLECT_DEFAULT_INTERVAL_MIN`

**Type:** integer (minutes) | **Default:** `30`

Default collection interval for newly added sources. Individual sources can override this via the source settings form (minimum: 5 minutes, maximum: 1440 minutes = 24 hours).

The collection scheduler runs every 5 minutes and collects from each source that is due (i.e., `now - last_collected_at >= collect_interval_min`).

---

## Docker-specific Notes

When using Docker Compose, set environment variables via the `.env` file (loaded automatically by Docker Compose):

```yaml
# docker-compose.yml
services:
  app:
    env_file:
      - .env
    environment:
      # Override DATABASE_URL to use the mounted volume
      - DATABASE_URL=sqlite+aiosqlite:///./data/cyberfeed.db
```

The `data/` directory is mounted as a volume to persist the SQLite database across container restarts:

```yaml
volumes:
  - ./data:/app/data
```

Create the directory before starting:
```bash
mkdir -p data
docker compose up -d
```

### Secrets in production

For production deployments, avoid putting secrets directly in `.env`. Consider:
- Docker secrets (`docker secret create`)
- A secrets manager (HashiCorp Vault, AWS Secrets Manager)
- Environment variables injected by your CI/CD system

The application reads all settings from environment variables, so any injection method that sets env vars will work.
