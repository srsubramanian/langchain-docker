FROM python:3.11-slim

WORKDIR /app

# Install uv for fast package management
RUN pip install uv

# Copy project files
COPY pyproject.toml README.md ./
COPY src ./src

# Install the package
RUN uv pip install --system -e .

# Run the application
CMD ["langchain-docker"]
