FROM python:3.11-slim

# Disable Python output buffering
ENV PYTHONUNBUFFERED=1

# 1. Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 2. Configure uv environment
ENV UV_PROJECT_ENVIRONMENT="/app/.venv"
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_COMPILE_BYTECODE=1

RUN apt-get update && apt-get install -y \
    wget unzip curl gnupg chromium chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 3. Install dependencies (Cached layer)
COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-install-project

# 4. Install project code
COPY . .

RUN uv sync --frozen

CMD ["sh", "-c", "python src/bot.py 2>&1 | tee logs/$(date +%Y-%m-%d_%H-%M-%S).log"]
