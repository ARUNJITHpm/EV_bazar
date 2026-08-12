"""Dump the OpenAPI schema to stdout.

    uv run python -m app.export_openapi > openapi.json
    npx openapi-typescript openapi.json -o frontend/src/api/schema.d.ts

CI runs both and fails if the committed ``schema.d.ts`` differs. A renamed
backend field must surface as a TypeScript error, not as an ``undefined``
where a rupee figure should be (AGENTS.md).

``sort_keys`` matters: without it the dump ordering can drift between runs
and CI reports spurious diffs.
"""

from __future__ import annotations

import json
import sys

from app.main import create_app


def main() -> None:
    schema = create_app().openapi()
    json.dump(schema, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
