# One image, two lives (STACK.md section 8):
#
#   * docker-compose: `api` and `poller` build this and override CMD, so the
#     compose services behave exactly as before - the frontend stage and the
#     Caddy binary just ride along unused.
#   * Hugging Face Space (talk-to/nitara): the default CMD runs
#     deploy/start.sh, which is the production topology in one container -
#     Caddy serves the built SPA and proxies /api to uvicorn on the loopback.
#     No Node process at runtime.

FROM node:24-slim@sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6 AS frontend-build
WORKDIR /build
# The public Mapbox token (pk.) is injected at build time, never committed.
# On the HF Space add VITE_MAPBOX_TOKEN as a Space VARIABLE (not a secret -
# it is a public client token, restricted by URL in the Mapbox console). If
# it is absent the build still succeeds; the public maps render an empty
# panel and the rest of the page works. See design/MAPBOX.md.
ARG PUBLIC_ANALYTICS_ORIGIN=""
ENV PUBLIC_ANALYTICS_ORIGIN=$PUBLIC_ANALYTICS_ORIGIN
ARG VITE_MAPBOX_TOKEN=""
ENV VITE_MAPBOX_TOKEN=$VITE_MAPBOX_TOKEN
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Only reviewed public analytics files enter the frontend build. Owner data,
# raw reference downloads and test fixtures are never copied into this stage.
COPY data/public/ /data/public/
RUN npm run build

FROM python:3.11-slim@sha256:bab1b7ef4b450c81002278d035eff85ebe394ae94df904f7a3ba14f7e16e487b

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
      gdal-bin \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc /uv /usr/local/bin/uv
COPY --from=caddy:2@sha256:0c994536bddb66445885237f1a5dcc1916bccea922661c76b4e9fc24061f9b52 /usr/bin/caddy /usr/local/bin/caddy

WORKDIR /srv

COPY pyproject.toml uv.lock ./
RUN uv export --frozen --no-dev --extra scrape --no-emit-project \
      --output-file /tmp/evsite-requirements.txt \
    && uv pip install --system --no-cache --require-hashes -r /tmp/evsite-requirements.txt

# Chromium renders the report to PDF, and that PDF is the archived artifact
# behind Rule 1. Pin the revision: a Chromium bump changes rasterisation and
# must therefore change renderer_version deliberately, never silently.
RUN playwright install --with-deps chromium

COPY . .
COPY --from=frontend-build /build/dist ./frontend/dist

EXPOSE 8000
CMD ["bash", "deploy/start.sh"]
