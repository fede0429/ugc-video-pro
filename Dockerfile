# ============================================================
# UGC Video Pro - Dockerfile
# ============================================================
# Multi-stage build for a lean production image.
# Base: Python 3.12 slim + FFmpeg + all Python deps.
#
# Build:  docker build -t ugc-video-pro .
# Run:    docker run --env-file .env -v $(pwd)/config.yaml:/app/config.yaml ugc-video-pro
# ============================================================

# ── Stage 1: Dependencies ────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# ── Stage 2: Runtime ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install FFmpeg and runtime system libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && ffmpeg -version | head -1

# Create non-root user for security
RUN groupadd -r ugcbot && useradd -r -g ugcbot -s /bin/false ugcbot

# Copy installed Python packages from builder
COPY --from=builder /root/.local /root/.local

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=ugcbot:ugcbot . .

# Create output directory
RUN mkdir -p /tmp/ugc_videos && chown ugcbot:ugcbot /tmp/ugc_videos

# Ensure Python path includes user packages
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Switch to non-root user
USER ugcbot

# Health check: verify the app starts cleanly
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import bot; import core; import models; import services; print('OK')" || exit 1

# Default command
CMD ["python", "main.py"]
