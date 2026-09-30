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

# Inventory is weekly, independent of the deferred five-minute status poller.
# Durable outcomes/ZIPs are in Postgres; restarts catch up the current due week.
if [ "${STATION_REFRESH_ENABLED:-true}" = "true" ]; then
  (
    while true; do
      python -m workers.data_refresh || echo "[start] data refresh worker exited; restarting"
      sleep 60
    done
  ) &
fi

# Owner-data retention (bill images, inactive accounts): daily, best-effort.
(
  while true; do
    python -m scripts.purge_owner_data || echo "[start] owner purge failed; retrying tomorrow"
    sleep 86400
  done
) &

# The poller: restart on exit, never silently gone (compose: restart: always).
# Status scraping is deferred - the only station data source in the initial stage
# is what owners upload - so it starts only when SCRAPER_ENABLED=true.
if [ "${SCRAPER_ENABLED:-false}" = "true" ]; then
  (
    while true; do
      python -m workers.poller || echo "[start] poller exited; restarting in 60s"
      sleep 60
    done
  ) &
fi

# Caddy owns the public port; if it dies, the Space restarts the container.
exec caddy run --config /srv/deploy/Caddyfile --adapter caddyfile
