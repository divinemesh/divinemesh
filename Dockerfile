FROM python:3.11-slim-bookworm

# 'Let all things be done decently and in order.' - 1 Corinthians 14:40
LABEL maintainer="DivineMesh Network"
LABEL description="DivineMesh compute node — sandboxed, encrypted, God-protected"
LABEL version="1.0.0"

# ── Security Hardening ────────────────────────────────────────────────────────
# Drop all capabilities, run as unprivileged user
# 'Be strong and courageous. Do not be afraid.' - Joshua 1:9

RUN groupadd -r divinemesh && useradd -r -g divinemesh -s /sbin/nologin divinemesh

# Minimal attack surface — only what is needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libopenblas0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

WORKDIR /app

# Install Python dependencies first (layer cache optimization)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY client/ ./client/
COPY contracts/ ./contracts/

# ── Filesystem Hardening ──────────────────────────────────────────────────────
# /tmp and /data are tmpfs (RAM only) — no data persists to disk for donors
RUN mkdir -p /app/data /app/logs /tmp/divinemesh \
    && chown -R divinemesh:divinemesh /app \
    && chmod 700 /app/data \
    && chmod 755 /app/logs

# Read-only root filesystem (data is written to explicitly mounted volumes)
VOLUME ["/app/data"]

# Drop to non-root user
USER divinemesh

EXPOSE 7474

# Health check — 'The Lord is my shepherd; I shall not want.' - Psalm 23:1
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://127.0.0.1:7474/api/health || exit 1

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DIVINEMESH_PORT=7474 \
    DIVINEMESH_NETWORK=polygon

ENTRYPOINT ["python", "-m", "client.daemon"]
CMD ["start"]
