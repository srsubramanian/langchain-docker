# Multi-stage Dockerfile for LangChain Docker application
# Supports both FastAPI backend and Chainlit UI

FROM python:3.11-slim as base

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
COPY pyproject.toml uv.lock* ./
COPY src/ ./src/
COPY chainlit_app/ ./chainlit_app/

# Install dependencies
RUN uv sync --frozen

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
