# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Install dependencies into /app/.venv
RUN uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Copy the environment from the builder
COPY --from=builder /app/.venv /app/.venv
# Copy your application source code
COPY . .

# Set the PATH to ensure the venv binaries are used
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
# Run the application using the environment's python to call the module
CMD ["/app/.venv/bin/python", "-m", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]


