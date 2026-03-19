FROM python:3.12-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies only (cached layer — no source needed yet)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application
COPY . .

# Install the project itself
RUN uv sync --frozen --no-dev

# Create data directory and make .venv accessible to any UID
RUN mkdir -p /app/data && chmod 777 /app/data && chmod -R a+rX /app/.venv

EXPOSE 8000

# Disable uv cache at runtime
ENV UV_NO_CACHE=1

CMD ["uv", "run", "uvicorn", "cyberfeed.main:app", "--host", "0.0.0.0", "--port", "8000"]
