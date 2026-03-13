# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv

WORKDIR /app
# Copy project files for dependency resolution
COPY pyproject.toml uv.lock ./
# Sync dependencies into a virtual environment
RUN /uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv
# Copy application code
COPY . .

# Set path to use the venv
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]