"""Export only district names/codes from a checksum-verified public LGD snapshot.

Does not touch the database or owners. Existing output is refused by default.
    uv run python -m scripts.export_public_districts
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

import pyarrow.parquet as pq


def main() -> None:
    source = Path("data/reference/districts.parquet")
    source_meta = json.loads(source.with_suffix(".meta.json").read_text(encoding="utf-8"))
    if hashlib.sha256(source.read_bytes()).hexdigest() != source_meta["sha256"]:
        raise ValueError("District snapshot differs from its recorded source checksum")
    destination = Path("data/public/district_reference")
    if (destination / "data.csv").exists() or (destination / "meta.json").exists():
        raise ValueError("Public reference already exists; review a replacement explicitly")
    rows = pq.read_table(source, columns=["dtname", "stname", "dist_lgd"]).to_pylist()
    records = []
    codes: set[int] = set()
    for row in rows:
        code = row["dist_lgd"]
        if code is None or code <= 0:
            continue
        if code in codes:
            raise ValueError(f"Duplicate district LGD code: {code}")
        codes.add(code)
        slug = re.sub(r"[^a-z0-9]+", "-", row["dtname"].lower()).strip("-")
        records.append([code, row["dtname"], row["stname"], f"{slug}-{code}", "[]"])
    destination.mkdir(parents=True, exist_ok=True)
    with (destination / "data.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["lgd_code", "district_name", "state_name", "slug", "former_names"])
        writer.writerows(sorted(records))
    columns = [
        {"name": name, "type": kind, "unit": unit, "description": description}
        for name, kind, unit, description in [
            ("lgd_code", "integer", "LGD district code", "Stable district join key in the source"),
            ("district_name", "string", "name", "District name as published in the snapshot"),
            ("state_name", "string", "name", "State name as published in the snapshot"),
            ("slug", "string", "URL slug", "District name plus LGD code for unique URLs"),
            ("former_names", "json", "names", "Verified aliases; empty until reviewed"),
        ]
    ]
    metadata = {
        "id": "district_reference",
        "title": "LGD district reference snapshot",
        "description": "District identifiers and names from the existing public LGD snapshot",
        "source_name": "Local Government Directory via india-geodata release",
        "source_url": source_meta["url"],
        "retrieved_on": source_meta["downloaded_at"][:10],
        "licence": "CC0-1.0 (india-geodata release files)",
        "licence_url": "https://creativecommons.org/publicdomain/zero/1.0/",
        "geography_level": "district",
        "time_coverage": "Source catalogue describes 2024 coverage; retrieved 2026-08-12",
        "update_frequency": "Refresh after reviewing a new LGD directory release",
        "notes": (
            "Historical snapshot, not a claim of current exhaustive district coverage. "
            "Two polygons without LGD codes are omitted. Former names are not inferred. "
            "Review renamed/split districts against the current official LGD directory. "
            "Release licence: https://github.com/yashveeeeeeer/india-geodata/"
            "blob/main/data/administrative/districts/README.md"
        ),
        "columns": columns,
        "source_sha256": source_meta["sha256"],
    }
    (destination / "meta.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Exported {len(records)} sourced district references; omitted {len(rows) - len(records)}"
    )


if __name__ == "__main__":
    main()
