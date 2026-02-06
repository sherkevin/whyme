# AgentOS Application Dockerfile
# Multi-stage build for optimized image size and performance

# Stage 1: Builder - Install UV and build dependencies
FROM python:3.11-slim AS builder

# Set environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_CACHE_DIR=/tmp/uv-cache

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install UV (fast Python package installer)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set working directory
WORKDIR /app

# Copy dependency files
COPY requirements.txt pyproject.toml ./

# Install dependencies using UV
RUN uv pip install --system -r requirements.txt && \
    rm -rf /tmp/uv-cache

# Stage 2: Runtime - Create final image
FROM python:3.11-slim

# Set labels
LABEL maintainer="AgentOS Team" \
      version="1.0.0" \
      description="AgentOS Core - Modular AI Agent Kernel"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    AGENTOS_SANDBOX=local \
    HOST=0.0.0.0 \
    PORT=8003

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Git for version control
    git \
    git-lfs \
    # Basic utilities
    curl \
    wget \
    jq \
    netcat-openbsd \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Create non-root user for security
RUN useradd -m -s /bin/bash -u 1000 agentos && \
    mkdir -p /app/data /app/data/uploads && \
    chown -R agentos:agentos /app

# Set working directory
WORKDIR /app

# Copy application files
COPY --chown=agentos:agentos src/ src/
COPY --chown=agentos:agentos scripts/ scripts/
COPY --chown=agentos:agentos pyproject.toml ./
COPY --chown=agentos:agentos README.md ./

# Create .env file if not exists
RUN if [ ! -f .env ]; then \
    echo "# AgentOS Environment Variables" > .env && \
    echo "DATABASE_URL=sqlite+aiosqlite:///./data/agentos.db" >> .env && \
    echo "HOST=0.0.0.0" >> .env && \
    echo "PORT=8003" >> .env && \
    echo "AGENTOS_SANDBOX=local" >> .env && \
    echo "LOG_LEVEL=info" >> .env; \
    fi

# Switch to non-root user
USER agentos

# Expose application port
EXPOSE 8003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8003/health || exit 1

# Default command - start the server
CMD ["python", "scripts/start.py"]
