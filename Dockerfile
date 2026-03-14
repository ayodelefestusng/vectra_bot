# Stage 1: Build
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Explicitly create and install into /app/.venv
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Copy the environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy application source
COPY . .

# Add to PATH
ENV PATH="/app/.venv/bin:$PATH"

# Run it
CMD ["python", "-m", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]