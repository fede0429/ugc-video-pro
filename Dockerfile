# ============================================================
# UGC Video Pro - Dockerfile
# ============================================================
# Multi-stage build for a lean production image.
#
# Stage 1 (builder): Compile Python wheels with build tools
# Stage 2 (runtime): Minimal Python 3.12 + FFmpeg + app code
#
# Build:  docker build -t ugc-video-pro .
# Run:    docker compose up -d
# ============================================================


# ── Stage 1: Builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install C build tools needed by some Python packages
# (cryptography, lxml, asyncpg, Pillow all need native code)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy requirements first to leverage Docker layer cache.
# Re-running pip install only when requirements.txt changes.
COPY requirements.txt .

# Install all Python dependencies into /root/.local
# --user keeps them separate from the system Python
RUN pip install --no-cache-dir --user -r requirements.txt


# ── Stage 2: Runtime ───────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install runtime-only system packages:
#   - ffmpeg: video processing (required by core/)
#   - curl: Docker healthcheck
#   - libpq5: PostgreSQL client library (asyncpg runtime dep)
#   - ca-certificates: HTTPS for API calls
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    libpq5 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ffmpeg -version 2>&1 | head -1

# Create a dedicated non-root user for security
RUN groupadd -r ugcapp && useradd -r -g ugcapp -s /bin/false ugcapp

# Copy compiled Python packages from the builder stage
COPY --from=builder /root/.local /root/.local

# Set application working directory
WORKDIR /app

# Copy entire application source
COPY --chown=ugcapp:ugcapp . .

# Create persistent data directories.
# These are mounted via Docker volume in production,
# but pre-creating them ensures correct ownership.
RUN mkdir -p /app/data/uploads /app/data/videos \
    && chown -R ugcapp:ugcapp /app/data

# Also create the legacy tmp dir used by the core orchestrator
RUN mkdir -p /tmp/ugc_videos && chown ugcapp:ugcapp /tmp/ugc_videos

# Python runtime environment
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Expose the FastAPI port
EXPOSE 8000

# Switch to non-root user
USER ugcapp

# Health check: hit the /api/health endpoint.
# start-period gives the app time to initialize the DB on first boot.
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Default command — start the FastAPI web server
CMD ["python", "main.py"]
