# Multi-stage Dockerfile for LangChain Docker application

# Configurable Python base image
# Override via: docker build --build-arg PYTHON_IMAGE=your-registry/python:3.13-slim .
ARG PYTHON_IMAGE=python:3.13-slim

FROM ${PYTHON_IMAGE} AS base

# Set working directory
WORKDIR /app

# Install uv for faster dependency management
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml ./
COPY README.md ./
COPY src/ ./src/

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

# Expose port for FastAPI backend
EXPOSE 8000

# Health check for FastAPI backend (using Python instead of curl)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Default command (can be overridden in docker-compose)
CMD ["uv", "run", "langchain-docker", "serve", "--host", "0.0.0.0", "--port", "8000"]
