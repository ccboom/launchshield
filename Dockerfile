# syntax=docker/dockerfile:1.6

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN adduser --disabled-password --gecos "" --uid 10001 appuser \
 && apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

COPY launchshield ./launchshield
COPY templates ./templates
COPY static ./static
COPY pytest.ini ./
COPY tests ./tests
COPY README.md ./

RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

ENV APP_ENV=production \
    HOST=0.0.0.0 \
    PORT=8000 \
    LAUNCHSHIELD_DATA_DIR=/app/data \
    LAUNCHSHIELD_DEMO_PACE_SECONDS=0.35

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT}/api/health || exit 1

CMD ["sh", "-c", "uvicorn launchshield.app:app --host ${HOST} --port ${PORT} --proxy-headers --forwarded-allow-ips '*'"]
