# Backend image. The frontend is a build artifact served by Caddy, not a
# service in this image (STACK.md section 8).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

RUN apt-get update && apt-get install -y --no-install-recommends \
      gdal-bin \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /srv

COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache -r pyproject.toml

# Chromium renders the report to PDF, and that PDF is the archived artifact
# behind Rule 1. Pin the revision: a Chromium bump changes rasterisation and
# must therefore change renderer_version deliberately, never silently.
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
