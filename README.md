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

Breakeven utilisation for EV charging sites in India, published to site
owners as **Chargeworthy**. FastAPI backend + one React SPA, PostGIS on
Neon. Station data comes from owner-uploaded bills; the charger-status
poller is a deferred later stage, off unless `SCRAPER_ENABLED=true`.

Every route below is the same SPA — public site, report and operations
console are route groups, not separate applications.

| Route | What it is |
|---|---|
| `/` | The Chargeworthy landing page. What we assess, what we do not claim, and the 34 factors named. |
| `/assess` | Drop a pin, answer four taps, get the utilisation the site must clear to break even. Pure arithmetic, no model, open (no login). |
| `/report/:id` | The full twelve-section assessment. Stored as JSONB and served verbatim — never recomputed. `/report/KL-TVM-DEMO-001` is the live demonstration. |
| `/owner` | Station owners: sign up or log in with a mobile number and a password, add one electricity bill, register the station once. Then `/owner/station/:id`, the station home page (last month, forecast range, trend, comparison with similar stations, money on the bill, forecast track record). |
| `/console` | The operations console. Login required. |

- Partner API under `/api/v1`, console API under `/api/internal`.
- Start with `OVERVIEW.md` for what the product is, `AGENTS.md` for the
  rules that will break it if you get them wrong.

Deployment notes: this Space runs the production topology in one container —
Caddy serves the built SPA and proxies `/api` to uvicorn (`deploy/start.sh`).
Configuration comes from Space secrets/variables (`DATABASE_URL`,
`CONSOLE_SECRET_KEY`, `CONSOLE_PASSWORD_HASH`, `ENV=prod`, ...); see
`app/config.py` for the full set.
