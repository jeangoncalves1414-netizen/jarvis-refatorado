#!/bin/sh
set -eu

# Caddy owns the public Railway port; Jarvis stays on two private loopback
# listeners (HTTP 8000 and streaming WebSocket 8001).
python -u -m app.main --server &
exec caddy run --config /app/deploy/railway/Caddyfile --adapter caddyfile
