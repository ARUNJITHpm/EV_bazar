#!/usr/bin/env bash
# HF Space entrypoint. One container carrying the docker-compose topology:
# Caddy is the public face on the Space port, uvicorn serves /api on the
# loopback, and the poller runs as its own process because it is its own
# reliability tier (docker-compose.yml: "web may go down for an hour, the
# poller may NOT").
set -e

cd /srv

# Schema first. Refuse to serve against a database we do not match.
alembic upgrade head

# Monthly partitions for the status/raw-payload tables. Idempotent. Tolerated
# on failure so a partition hiccup does not take the console down with it -
# the poller will fail loudly on write if partitions are genuinely missing.
python -m scripts.ensure_partitions || echo "[start] ensure_partitions failed; continuing"

# API on the loopback; Caddy proxies /api here.
uvicorn app.main:app --host 127.0.0.1 --port 8001 &

# The poller: restart on exit, never silently gone (compose: restart: always).
(
  while true; do
    python -m workers.poller || echo "[start] poller exited; restarting in 60s"
    sleep 60
  done
) &

# Caddy owns the public port; if it dies, the Space restarts the container.
exec caddy run --config /srv/deploy/Caddyfile --adapter caddyfile
