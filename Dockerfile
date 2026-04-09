# Multi-stage build for efficient Docker image
FROM python:3.12-slim as builder

# Install system dependencies for PySpark
RUN apt-get update && apt-get install -y \
    default-jre-headless \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set Java home
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production runtime stage
FROM python:3.12-slim

# Install runtime dependencies only (including curl for health checks)
RUN apt-get update && apt-get install -y \
    default-jre-headless \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set Java home
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Create non-root user
RUN useradd -m -u 1000 appuser

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code with ownership
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser . .

# Pre-create writable directories for appuser (logs, data for SQLite)
RUN mkdir -p /app/logs /app/data \
    && chown -R appuser:appuser /app/logs /app/data \
    && chmod -R 755 /app/logs /app/data

# Switch to non-root user
USER appuser

# Set default port (Cloud Run overrides via PORT env var or defaults to 8080)
ENV PORT=8080

# Expose API port
EXPOSE ${PORT}

# Health check (simplified - just check if port is listening)
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run the API server with PORT from environment
ENTRYPOINT exec python -m uvicorn src.api:app --host 0.0.0.0 --port $PORT
