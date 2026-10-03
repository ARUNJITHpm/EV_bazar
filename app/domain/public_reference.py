"""Read-only access to the same public files validated by the frontend build.

No acquisition, inference, SQL, or runtime Node. A release pins the offline
snapshot digest; source bytes must still match that snapshot at startup.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, cast

Json: TypeAlias = None | bool | int | float | str | list["Json"] | dict[str, "Json"]
Row: TypeAlias = dict[str, Json]
EXPANSION_DATASETS = (
    "discom_performance",
    "supply_hours",
    "state_ev_policies",
    "nhai_wayside_amenities",
    "osm_power",
    "cea_ev_consumption",
)
_VERSIONS = {
    "model_version": "not_applicable:observed_public_data",
    "economics_version": "not_applicable:no_economics_computation",
    "schema_version": "public_analytics_v2",
    "archetype_version": "not_applicable:public_data",
    "tariff_effective_date": "per_row:effective_from_for_tariffs;not_applicable_otherwise",
    "renderer_version": "public_data_export_v2",
}


def _object(value: Json) -> Row:
    if not isinstance(value, dict):
        raise ValueError("Reference object required")
    return value


def _inside(root: Path, path: Path) -> Path:
    resolved = path.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("Reference source escapes its public root")
    return resolved


@dataclass(frozen=True)
class ReferenceResult:
    dataset: str
    status: str
    rows: tuple[Row, ...]
    provenance: Row | None
    versions: dict[str, str]
    snapshot_sha256: str


class PublicReference:
    def __init__(self, snapshot: Row, digest: str) -> None:
        self._snapshot = copy.deepcopy(snapshot)
        self._digest = digest

    @classmethod
    def load(
        cls, snapshot_path: Path, source_root: Path, *, expected_sha256: str
    ) -> PublicReference:
        """Fail closed on unpinned, fixture, stale or modified release inputs."""
        if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
            raise ValueError("A release-pinned SHA256 is required")
        data = snapshot_path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != expected_sha256:
            raise ValueError("Reference snapshot digest differs from release")
        snapshot = _object(cast(Json, json.loads(data)))
        if snapshot.get("fixture") is not False:
            raise ValueError("Fixture reference refused")
        catalogue = _object(snapshot.get("catalogue"))
        if catalogue.get("versions") != _VERSIONS:
            raise ValueError("Unsupported reference versions")
        datasets = _object(snapshot.get("datasets"))
        descriptors = catalogue.get("datasets")
        if not isinstance(descriptors, list):
            raise ValueError("Missing dataset catalogue")
        if set(datasets) != {_object(item).get("id") for item in descriptors}:
            raise ValueError("Snapshot and catalogue disagree")
        root = source_root.resolve(strict=True)
        for name, value in datasets.items():
            if name not in (
                *EXPANSION_DATASETS,
                "district_reference",
                "rto_to_district",
                "ev_registrations",
                "public_chargers",
                "ev_tariffs",
                "district_boundaries",
                "highways",
            ):
                raise ValueError("Unknown reference dataset")
            item = _object(value)
            metadata = _object(item.get("metadata"))
            if metadata.get("fixture"):
                raise ValueError("Fixture metadata refused")
            data_filename = {
                "district_boundaries": "data.topojson",
                "highways": "data.geojson",
            }.get(name, "data.csv")
            for filename, key in ((data_filename, "raw_sha256"), ("meta.json", "metadata_sha256")):
                source = _inside(root, root / name / filename).read_bytes()
                if hashlib.sha256(source).hexdigest() != item.get(key):
                    raise ValueError(f"Reference source changed: {name}/{filename}")
            rows = item.get("rows")
            if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
                raise ValueError("Reference rows required")
        # Also refuse sources activated after export: a stale pending snapshot
        # must not silently conceal a new live dataset.
        for name in EXPANSION_DATASETS:
            if name not in datasets and any(
                (root / name / f).exists() for f in ("data.csv", "meta.json")
            ):
                raise ValueError(f"Reference activation changed: {name}")
        return cls(snapshot, digest)

    def lookup(
        self,
        dataset: str,
        *,
        state: str | None = None,
        lgd_code: int | None = None,
        discom_id: str | None = None,
    ) -> ReferenceResult:
        """Return area context, never assign a site's serving utility.

        District lookup includes wider state/utility context at its original
        scope; utility-wide observations do not acquire district scope. OSM points
        without a reviewed LGD join do not acquire state/district scope.
        Policy selection returns dated history; it does not assert eligibility.
        """
        if dataset not in EXPANSION_DATASETS:
            raise ValueError("Unsupported expansion dataset")
        data = _object(self._snapshot.get("datasets"))
        value = data.get(dataset)
        if value is None:
            return ReferenceResult(dataset, "pending", (), None, dict(_VERSIONS), self._digest)
        item = _object(value)
        rows = cast(list[Row], item["rows"])
        reference = data.get("district_reference")
        districts = cast(list[Row], _object(reference).get("rows", [])) if reference else []
        states = {cast(int, row["lgd_code"]): cast(str, row["state_name"]) for row in districts}
        if lgd_code is not None:
            district_state = states.get(lgd_code)
            if state is not None and district_state is not None and state != district_state:
                raise ValueError("District/state mismatch")
            if district_state is None:
                return ReferenceResult(
                    dataset,
                    "no_matching_observations",
                    (),
                    copy.deepcopy(_object(item.get("metadata"))),
                    dict(_VERSIONS),
                    self._digest,
                )
            state = district_state
        selected: list[Row] = []
        for row in rows:
            code = row.get("lgd_code")
            row_state = row.get("state") or (states.get(code) if isinstance(code, int) else None)
            if state is not None and row_state not in (state, "central"):
                continue
            if lgd_code is not None and code is not None and code != lgd_code:
                continue
            if discom_id is not None and row.get("discom_id") != discom_id:
                continue
            selected.append(copy.deepcopy(row))
        return ReferenceResult(
            dataset,
            "available" if selected else "no_matching_observations",
            tuple(selected),
            copy.deepcopy(_object(item.get("metadata"))),
            dict(_VERSIONS),
            self._digest,
        )
