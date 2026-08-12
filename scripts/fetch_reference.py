"""Download the reference layers - PART 1.2.

    uv run python -m scripts.fetch_reference            # all layers
    uv run python -m scripts.fetch_reference districts  # just one

Files land in ``data/reference/`` (gitignored - they are tens of MB and are
reproducible from this script). Alongside each, a ``.meta.json`` records the
URL, the SHA-256 and the moment it was fetched, so ``load_reference`` can
stamp the provenance into ``reference_layers`` without re-deriving it.

Already-downloaded files are skipped unless ``--force``. A re-download that
produces a different checksum is reported rather than silently accepted: the
boundaries changing underneath us is news, not a detail.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

import httpx

from app.domain.resolution.reference import BY_NAME, LAYERS, LayerSpec

DEST = pathlib.Path("data/reference")


def _paths(layer: LayerSpec) -> tuple[pathlib.Path, pathlib.Path]:
    return DEST / f"{layer.name}.parquet", DEST / f"{layer.name}.meta.json"


def fetch(layer: LayerSpec, *, force: bool = False) -> pathlib.Path:
    path, meta_path = _paths(layer)
    DEST.mkdir(parents=True, exist_ok=True)

    if path.exists() and not force:
        print(f"{layer.name:<12} already present ({path.stat().st_size / 1e6:.1f} MB), skipping")
        return path

    print(f"{layer.name:<12} downloading {layer.url}")
    digest = hashlib.sha256()
    # Streamed to a temporary name so an interrupted download never leaves a
    # truncated file that looks complete on the next run.
    tmp = path.with_suffix(".partial")
    with httpx.stream("GET", layer.url, follow_redirects=True, timeout=300) as response:
        response.raise_for_status()
        with tmp.open("wb") as handle:
            for chunk in response.iter_bytes(1 << 20):
                handle.write(chunk)
                digest.update(chunk)

    sha = digest.hexdigest()
    previous = None
    if meta_path.exists():
        previous = json.loads(meta_path.read_text()).get("sha256")

    tmp.replace(path)
    meta_path.write_text(
        json.dumps(
            {
                "layer": layer.name,
                "url": layer.url,
                "licence": layer.licence,
                "sha256": sha,
                "bytes": path.stat().st_size,
                "downloaded_at": dt.datetime.now(dt.UTC).isoformat(),
            },
            indent=2,
        )
    )

    print(f"{layer.name:<12} {path.stat().st_size / 1e6:8.1f} MB  sha256={sha[:16]}…")
    if previous and previous != sha:
        print(
            f"{layer.name:<12} ⚠ CONTENT CHANGED since the last fetch (was {previous[:16]}…).\n"
            f"{'':<12}   Boundaries moving is a real event - check what changed before "
            f"reloading, and expect old reports to reference the old vintage."
        )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch reference geography (PLAN 1.2)")
    parser.add_argument("layers", nargs="*", help="layer names; default all")
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    args = parser.parse_args(argv)

    if args.layers:
        unknown = [name for name in args.layers if name not in BY_NAME]
        if unknown:
            print(f"unknown layer(s): {', '.join(unknown)}; known: {', '.join(BY_NAME)}")
            return 2
        selected = [BY_NAME[name] for name in args.layers]
    else:
        selected = list(LAYERS)

    for layer in selected:
        fetch(layer, force=args.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
