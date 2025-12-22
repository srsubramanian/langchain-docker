# Multi-stage Dockerfile for LangChain Docker application
# Supports both FastAPI backend and Chainlit UI

FROM python:3.11-slim AS base

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/
COPY chainlit_app/ ./chainlit_app/

# Copy lock file if it exists
COPY uv.lock* ./

# Install dependencies
# Use --frozen if lock file exists, otherwise create it
RUN if [ -f uv.lock ]; then \
        uv sync --frozen; \
    else \
        uv sync; \
    fi

# Copy environment file (template)
COPY .env.example .env.example

# Expose ports
# 8000 for FastAPI backend
# 8001 for Chainlit UI
EXPOSE 8000 8001

# Health check for FastAPI backend
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "langchain-docker", "serve", "--host", "0.0.0.0", "--port", "8000"]
