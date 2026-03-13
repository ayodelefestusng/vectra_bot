# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Install into /app/.venv
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app
# Copy the installed dependencies from the builder
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Set the environment variable to point to the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Use python to call the module directly to avoid path issues
CMD ["python", "-m", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]