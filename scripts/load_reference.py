"""Load the reference layers into PostGIS - PART 1.2.

    uv run python -m scripts.fetch_reference
    uv run python -m scripts.load_reference            # all layers
    uv run python -m scripts.load_reference districts  # just one

Each layer is replaced wholesale inside one transaction, and its provenance
row in ``reference_layers`` is written in the same transaction. There is no
partial state: either the new boundaries and the record of where they came
from both land, or neither does.

Geometry is read as WKB from GeoParquet and repaired on the way in:

    ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_GeomFromWKB(...)), 3))

  ST_MakeValid        published administrative boundaries routinely contain
                      self-intersections. An invalid polygon does not error
                      on insert - it errors later, inside ST_Contains, on one
                      unlucky site, months from now.
  ST_CollectionExtract repairing a bow-tie can yield a GeometryCollection of
                      polygons plus zero-area lines and points. Type 3 keeps
                      the polygons. The discarded slivers have no area, so no
                      site can fall inside one - but the count of features
                      that needed repair is printed rather than swallowed,
                      because "the source needed fixing" is worth knowing.
  ST_Multi            the column is MULTIPOLYGON; some features arrive as
                      plain POLYGON and would otherwise be rejected.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pyarrow.parquet as pq
import shapely
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.domain.resolution.reference import BY_NAME, GEOMETRY_COLUMN, LAYERS, LayerSpec

SOURCE_DIR = pathlib.Path("data/reference")
#: Rows per INSERT. Large enough that 19k pincodes is a handful of round
#: trips, small enough that a single statement's parameters stay sane.
BATCH = 500

#: WKB -> a valid MULTIPOLYGON in EPSG:4326. See the module docstring for why
#: each step is here; every geometry column in PLAN 1.2 uses this same chain.
GEOM_SQL = "ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_GeomFromWKB(:wkb, 4326)), 3))"


@dataclass(frozen=True)
class LoadResult:
    loaded: int
    skipped: int
    #: Features the publisher shipped invalid, which PostGIS had to repair.
    repaired: int


def _needs_repair(wkb: bytes) -> bool:
    """Was the source geometry invalid as published?

    Checked locally with Shapely rather than by asking the database, so
    counting repairs costs CPU we already have instead of a round trip per
    row. Reported, not silenced: a source that starts needing far more repair
    than last time has changed in a way worth looking at.
    """
    try:
        return not shapely.from_wkb(wkb).is_valid
    except Exception:  # noqa: BLE001 - unreadable WKB is Postgres's problem to report
        return True


def _batches(path: pathlib.Path, columns: tuple[str, ...]) -> Iterator[list[dict[str, Any]]]:
    """Stream a Parquet file in batches, reading only the columns we need."""
    parquet = pq.ParquetFile(path)
    for batch in parquet.iter_batches(batch_size=BATCH, columns=list(columns)):
        yield batch.to_pylist()


def _meta(layer: LayerSpec) -> dict[str, Any]:
    meta_path = SOURCE_DIR / f"{layer.name}.meta.json"
    if not meta_path.exists():
        raise SystemExit(
            f"{layer.name}: no {meta_path}. Run `uv run python -m scripts.fetch_reference "
            f"{layer.name}` first - loading without recorded provenance is not allowed "
            f"(Rule 1)."
        )
    result: dict[str, Any] = json.loads(meta_path.read_text())
    return result


def _record_layer(session: Session, layer: LayerSpec, meta: dict[str, Any], count: int) -> None:
    session.execute(
        text(
            """
            INSERT INTO reference_layers
                (name, source_url, sha256, licence, feature_count, downloaded_at, loaded_at, note)
            VALUES (:name, :url, :sha, :licence, :count, :downloaded_at, :loaded_at, :note)
            ON CONFLICT (name) DO UPDATE SET
                source_url = EXCLUDED.source_url,
                sha256 = EXCLUDED.sha256,
                licence = EXCLUDED.licence,
                feature_count = EXCLUDED.feature_count,
                downloaded_at = EXCLUDED.downloaded_at,
                loaded_at = EXCLUDED.loaded_at,
                note = EXCLUDED.note
            """
        ),
        {
            "name": layer.name,
            "url": meta["url"],
            "sha": meta["sha256"],
            "licence": layer.licence,
            "count": count,
            "downloaded_at": dt.datetime.fromisoformat(meta["downloaded_at"]),
            "loaded_at": dt.datetime.now(dt.UTC),
            "note": layer.note,
        },
    )


# --- per-layer loaders ------------------------------------------------------
#
# One function per layer rather than a generic mapper. The layers genuinely
# differ - column casing, which rows to skip, what counts as a key - and a
# configurable mapper would hide those differences instead of documenting them.


def load_states(session: Session, layer: LayerSpec, path: pathlib.Path) -> LoadResult:
    session.execute(text("DELETE FROM states"))
    loaded = skipped = repaired = 0
    for rows in _batches(path, layer.columns):
        payload = []
        for row in rows:
            code = row.get("State_LGD")
            if not code:
                skipped += 1
                continue
            payload.append(
                {
                    "code": int(code),
                    "name": (row.get("STNAME") or "").strip(),
                    "census": (row.get("STCODE11") or "").strip() or None,
                    "wkb": row[GEOMETRY_COLUMN],
                }
            )
            repaired += _needs_repair(row[GEOMETRY_COLUMN])
        if payload:
            session.execute(
                text(
                    """
                    INSERT INTO states (lgd_state_code, name, census_2011_code, geom)
                    VALUES (:code, :name, :census, """
                    + GEOM_SQL
                    + """)
                    ON CONFLICT (lgd_state_code) DO NOTHING
                    """
                ),
                payload,
            )
            loaded += len(payload)
    return LoadResult(loaded, skipped, repaired)


def load_districts(session: Session, layer: LayerSpec, path: pathlib.Path) -> LoadResult:
    # Districts reference states, so the delete order matters and the
    # crosswalk's FK has to let go first.
    session.execute(text("UPDATE district_name_crosswalk SET lgd_district_code = NULL"))
    session.execute(text("DELETE FROM districts"))

    known_states = {
        int(code) for code in session.execute(text("SELECT lgd_state_code FROM states")).scalars()
    }

    loaded = skipped = repaired = 0
    for rows in _batches(path, layer.columns):
        payload = []
        for row in rows:
            code = row.get("dist_lgd")
            state = row.get("state_lgd")
            # Two J&K rows cover PoK-administered districts and carry no LGD
            # code. They are claimed territory with no Indian administration,
            # so there is nothing to attribute a site to; skipping is correct.
            if not code or not state or int(state) not in known_states:
                skipped += 1
                continue
            payload.append(
                {
                    "code": int(code),
                    "state": int(state),
                    "name": (row.get("dtname") or "").strip(),
                    "state_name": (row.get("stname") or "").strip(),
                    "census": (row.get("dtcode11") or "").strip() or None,
                    "vintage": (row.get("year_stat") or "").strip() or None,
                    "wkb": row[GEOMETRY_COLUMN],
                }
            )
            repaired += _needs_repair(row[GEOMETRY_COLUMN])
        if payload:
            session.execute(
                text(
                    """
                    INSERT INTO districts
                        (lgd_district_code, lgd_state_code, name, state_name,
                         census_2011_code, boundary_vintage, geom)
                    VALUES (:code, :state, :name, :state_name, :census, :vintage,
                            """
                    + GEOM_SQL
                    + """)
                    ON CONFLICT (lgd_district_code) DO NOTHING
                    """
                ),
                payload,
            )
            loaded += len(payload)
    return LoadResult(loaded, skipped, repaired)


def load_pincodes(session: Session, layer: LayerSpec, path: pathlib.Path) -> LoadResult:
    session.execute(text("DELETE FROM pincodes"))
    loaded = skipped = repaired = 0
    for rows in _batches(path, layer.columns):
        payload = []
        for row in rows:
            pin = (row.get("Pincode") or "").strip()
            if len(pin) != 6 or not pin.isdigit():
                skipped += 1
                continue
            payload.append(
                {
                    "pin": pin,
                    "office": (row.get("Office_Name") or "").strip() or None,
                    "circle": (row.get("Circle") or "").strip() or None,
                    "region": (row.get("Region") or "").strip() or None,
                    "division": (row.get("Division") or "").strip() or None,
                    "wkb": row[GEOMETRY_COLUMN],
                }
            )
            repaired += _needs_repair(row[GEOMETRY_COLUMN])
        if payload:
            session.execute(
                text(
                    """
                    INSERT INTO pincodes
                        (pincode, office_name, postal_circle, postal_region,
                         postal_division, geom)
                    VALUES (:pin, :office, :circle, :region, :division, """
                    + GEOM_SQL
                    + """)
                    """
                ),
                payload,
            )
            loaded += len(payload)
    return LoadResult(loaded, skipped, repaired)


LOADERS = {
    "states": load_states,
    "districts": load_districts,
    "pincodes": load_pincodes,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load reference geography (PLAN 1.2)")
    parser.add_argument("layers", nargs="*", help="layer names; default all, in dependency order")
    args = parser.parse_args(argv)

    if args.layers:
        unknown = [n for n in args.layers if n not in BY_NAME]
        if unknown:
            print(f"unknown layer(s): {', '.join(unknown)}; known: {', '.join(BY_NAME)}")
            return 2
        # Registry order, not command-line order: districts have a foreign key
        # to states and loading them the other way round simply fails.
        selected = [layer for layer in LAYERS if layer.name in set(args.layers)]
    else:
        selected = list(LAYERS)

    for layer in selected:
        path = SOURCE_DIR / f"{layer.name}.parquet"
        if not path.exists():
            print(f"{layer.name}: {path} missing - run scripts.fetch_reference first")
            return 1

        meta = _meta(layer)
        with SessionLocal() as session:
            result = LOADERS[layer.name](session, layer, path)
            _record_layer(session, layer, meta, result.loaded)
            session.commit()

        notes = []
        if result.skipped:
            notes.append(f"{result.skipped} skipped")
        if result.repaired:
            notes.append(f"{result.repaired} invalid in source, repaired")
        suffix = f"  ({', '.join(notes)})" if notes else ""
        print(f"{layer.name:<12} {result.loaded:>6} features loaded{suffix}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
