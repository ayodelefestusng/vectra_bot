FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy the application into the container.
COPY . /app

# Set working directory to /app
WORKDIR /app

# Install the application dependencies.
RUN uv sync --frozen --no-cache

# Run the application.
# Now correctly pointing to main.py at the root of /app
CMD ["/app/.venv/bin/fastapi", "run", "main.py", "--port", "80", "--host", "0.0.0.0"]