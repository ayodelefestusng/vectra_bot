# Stage 1: Build dependencies
FROM python:3.11-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./

# Create the venv explicitly and install dependencies
RUN uv venv /app/.venv && \
    . /app/.venv/bin/activate && \
    uv sync --frozen --no-dev --no-install-project

# Stage 2: Runtime
FROM python:3.11-slim
WORKDIR /app

# Copy only the venv from the builder
COPY --from=builder /app/.venv /app/.venv
COPY . .

# Set the environment variable to ensure python finds the modules
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
# Run using the absolute path to the venv python
CMD ["/app/.venv/bin/python", "-m", "fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]