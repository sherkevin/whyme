# AgentOS Ubuntu Runtime Environment
# Multi-user isolated sandbox with AI-friendly tools

FROM docker.1ms.run/library/ubuntu:22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # Python and development tools
    python3.11 \
    python3.11-dev \
    python3-pip \
    python3-venv \
    # Build essentials
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    # Version control
    git \
    git-lfs \
    # Editors and utilities
    vim \
    nano \
    curl \
    wget \
    unzip \
    zip \
    # Network tools
    netcat-openbsd \
    iputils-ping \
    # File processing
    jq \
    tree \
    # Node.js (for web development)
    nodejs \
    npm \
    # Additional languages
    golang-go \
    rustc \
    cargo \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -s /bin/bash -u 1000 agentuser

# Set up Python environment
RUN python3.11 -m pip install --upgrade pip setuptools wheel

# Install common Python packages for AI/ML work
RUN pip3 install \
    # Core data science
    numpy \
    pandas \
    scipy \
    matplotlib \
    seaborn \
    # Machine learning
    scikit-learn \
    # Web frameworks
    fastapi \
    flask \
    requests \
    # Database
    sqlalchemy \
    # Testing
    pytest \
    pytest-asyncio \
    # Code quality
    black \
    flake8 \
    pylint \
    # Utilities
    python-dotenv \
    pydantic

# Create workspace directory
RUN mkdir -p /workspace && chown -R agentuser:agentuser /workspace

# Set workspace as working directory
WORKDIR /workspace

# Switch to non-root user
USER agentuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 --version || exit 1

# Keep container running
CMD ["sleep", "infinity"]
