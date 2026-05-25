# syntax=docker/dockerfile:1.7
# Multi-stage build for Task B Recommendation Service

# Stage 1: Builder stage
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV TORCH_VERSION=2.5.1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY task_b/requirements.txt /tmp/task_b_requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --index-url https://download.pytorch.org/whl/cpu "torch==${TORCH_VERSION}" && \
    pip install -r /tmp/task_b_requirements.txt

# Stage 2: Runtime stage
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV PATH="/opt/venv/bin:$PATH"
ENV CHROMA_PERSIST_DIR=/app/chroma_db

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY shared/ /app/shared/
COPY task_b/ /app/task_b/
COPY chroma_db/ /app/chroma_db/

# Set ownership to non-root user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8002/health')"

# Expose port
EXPOSE 8002

# Run the application
CMD ["uvicorn", "task_b.main:app", "--host", "0.0.0.0", "--port", "8002"]
