---
title: EV Bazar
emoji: ⚡
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8000
pinned: false
---

# EV Site Intelligence Platform

Breakeven utilisation for EV charging sites in India. FastAPI backend +
React console SPA, PostGIS on Neon. Station data comes from owner-uploaded
bills; the charger-status poller is a deferred later stage, off unless
`SCRAPER_ENABLED=true`.

- Station owners sign up or log in at `/owner` (mobile number and a password), add a
  bill, and get their station's home page at `/owner/station/:id`.
- The operations console lives at `/console` (login required).
- Partner API under `/api/v1`, console API under `/api/internal`.

Deployment notes: this Space runs the production topology in one container —
Caddy serves the built SPA and proxies `/api` to uvicorn (`deploy/start.sh`).
Configuration comes from Space secrets/variables (`DATABASE_URL`,
`CONSOLE_SECRET_KEY`, `CONSOLE_PASSWORD_HASH`, `ENV=prod`, ...); see
`app/config.py` for the full set.
