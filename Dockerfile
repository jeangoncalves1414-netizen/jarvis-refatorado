# Build the same React panel used on desktop inside the deploy image.
FROM node:22-bookworm AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM caddy:2.8-alpine AS caddy

FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    JARVIS_CLOUD=1 \
    APP_HOST=127.0.0.1 \
    APP_PORT=8000 \
    APP_DATA_DIR=/app/data

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy

COPY pyproject.toml ./
COPY app/ ./app/
RUN pip install --no-cache-dir .
COPY deploy/ ./deploy/
COPY --from=frontend /build/frontend/dist ./frontend/dist
RUN chmod +x /app/deploy/railway/start.sh

CMD ["/app/deploy/railway/start.sh"]
