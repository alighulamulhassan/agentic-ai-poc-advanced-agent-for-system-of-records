# ============================================================
# Enterprise Agent — Multi-stage Dockerfile
# ============================================================
# Stage 1: Builder — install all dependencies
# Stage 2: Production — minimal runtime image
#
# Build: docker build -t enterprise-agent .
# Run:   docker run -p 8000:8000 --env-file .env enterprise-agent
# ============================================================

# ---------- Stage 1: Builder ----------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install into a prefix
COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --prefix=/install --no-cache-dir -r requirements.txt

# ---------- Stage 2: Production ----------
FROM python:3.12-slim AS production

LABEL org.opencontainers.image.title="Enterprise Agent"
LABEL org.opencontainers.image.description="Agentic AI for System of Records"
LABEL org.opencontainers.image.version="2.0.0"

WORKDIR /app

# Runtime system dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r agent && useradd -r -g agent agent

# Copy application code
COPY backend/app ./app
COPY backend/data ./data

# Create data directories
RUN mkdir -p data/db data/chroma data/documents data/audio && \
    chown -R agent:agent /app

# Switch to non-root
USER agent

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Environment defaults (override via .env or ECS task definition)
ENV ENVIRONMENT=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Start
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
