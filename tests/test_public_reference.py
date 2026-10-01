"""Backend reads Node-validated release data without Node in request handling."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.domain.public_reference import EXPANSION_DATASETS, PublicReference
from scripts.compare_public_policies import compare

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def release(tmp_path):
    sources = tmp_path / "public"
    shutil.copytree(REPO / "data/fixtures", sources)
    # Synthetic test source isolated in tmp_path. Never written to data/public.
    for path in sources.rglob("*"):
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            text = text.replace('"fixture": true', '"fixture": false')
            text = text.replace("Test ", "Synthetic ").replace(
                "example.invalid", "data.example.org"
            )
            path.write_text(text, encoding="utf-8")
    snapshot = tmp_path / "snapshot.json"
    subprocess.run(
        [
            "node",
            str(REPO / "frontend/scripts/export-public-reference.ts"),
            str(sources),
            str(snapshot),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    return sources, snapshot, digest


@pytest.mark.parametrize("dataset", EXPANSION_DATASETS)
def test_every_dataset_has_state_and_district_context(release, dataset):
    sources, snapshot, digest = release
    reference = PublicReference.load(snapshot, sources, expected_sha256=digest)
    by_state = reference.lookup(dataset, state="Synthetic State")
    by_district = reference.lookup(dataset, lgd_code=999001)
    assert by_state.status == by_district.status == "available"
    assert by_state.rows == by_district.rows
    assert by_state.snapshot_sha256 == digest
    assert len(by_state.versions) == 6
    assert by_state.provenance["review_ref"] == "Synthetic human review"


def test_area_averages_stay_area_averages_and_do_not_assign_discom(release):
    sources, snapshot, digest = release
    reference = PublicReference.load(snapshot, sources, expected_sha256=digest)
    row = reference.lookup("supply_hours", lgd_code=999001).rows[0]
    assert row["lgd_code"] is None
    assert row["discom_id"] is None
    assert row["period_type"] == "fiscal_year"
    assert reference.lookup("discom_performance", discom_id="unverified").rows == ()
    assert reference.lookup("supply_hours", lgd_code=1).rows == ()
    with pytest.raises(ValueError, match="mismatch"):
        reference.lookup("supply_hours", lgd_code=999001, state="Wrong State")


def test_results_cannot_mutate_next_lookup(release):
    sources, snapshot, digest = release
    reference = PublicReference.load(snapshot, sources, expected_sha256=digest)
    result = reference.lookup("state_ev_policies")
    result.rows[0]["policy_name"] = "changed"
    result.versions["schema_version"] = "changed"
    result.provenance["licence"] = "changed"
    again = reference.lookup("state_ev_policies")
    assert again.rows[0]["policy_name"] != "changed"
    assert again.versions["schema_version"] == "public_analytics_v2"
    assert again.provenance["licence"] != "changed"


def test_snapshot_digest_is_required_and_verified(release):
    sources, snapshot, digest = release
    with pytest.raises(ValueError, match="pinned"):
        PublicReference.load(snapshot, sources, expected_sha256="")
    snapshot.write_bytes(snapshot.read_bytes() + b" ")
    with pytest.raises(ValueError, match="digest"):
        PublicReference.load(snapshot, sources, expected_sha256=digest)


@pytest.mark.parametrize("filename", ["supply_hours/data.csv", "osm_power/meta.json"])
def test_stale_source_and_metadata_refused(release, filename):
    sources, snapshot, digest = release
    path = sources / filename
    path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="source changed"):
        PublicReference.load(snapshot, sources, expected_sha256=digest)


@pytest.mark.parametrize(
    "patch, message",
    [
        ({"fixture": True}, "Fixture"),
        ({"fixture": None}, "Fixture"),
        ({"bad_version": True}, "versions"),
    ],
)
def test_unsupported_or_fixture_snapshot_refused_even_with_new_digest(release, patch, message):
    sources, snapshot, _ = release
    data = json.loads(snapshot.read_bytes())
    if patch.pop("bad_version", False):
        data["catalogue"]["versions"]["schema_version"] = "old"
    else:
        data.update(patch)
    snapshot.write_text(json.dumps(data), encoding="utf-8")
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match=message):
        PublicReference.load(snapshot, sources, expected_sha256=digest)


def test_pending_production_sources_return_no_invented_values(tmp_path):
    snapshot = tmp_path / "snapshot.json"
    sources = REPO / "data/public"
    subprocess.run(
        [
            "node",
            str(REPO / "frontend/scripts/export-public-reference.ts"),
            str(sources),
            str(snapshot),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    reference = PublicReference.load(snapshot, sources, expected_sha256=digest)
    for dataset in EXPANSION_DATASETS:
        result = reference.lookup(dataset, state="Kerala")
        assert result.status == "pending"
        assert result.rows == () and result.provenance is None


def test_activation_after_export_is_refused(release):
    sources, snapshot, _ = release
    # Export a genuinely pending source, then activate it afterwards.
    stored = (sources / "supply_hours/meta.json").read_bytes()
    (sources / "supply_hours/meta.json").unlink()
    (sources / "supply_hours/data.csv").unlink()
    subprocess.run(
        [
            "node",
            str(REPO / "frontend/scripts/export-public-reference.ts"),
            str(sources),
            str(snapshot),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    (sources / "supply_hours/meta.json").write_bytes(stored)
    with pytest.raises(ValueError, match="activation changed"):
        PublicReference.load(snapshot, sources, expected_sha256=digest)


def test_reference_source_symlink_escape_is_refused(release, tmp_path):
    sources, snapshot, digest = release
    path = sources / "supply_hours"
    outside = tmp_path / "outside"
    shutil.copytree(path, outside)
    assert path.resolve().is_relative_to(tmp_path.resolve())
    shutil.rmtree(path)
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(path), str(outside)],
            check=True,
            capture_output=True,
        )
    else:
        path.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="escapes"):
        PublicReference.load(snapshot, sources, expected_sha256=digest)


def test_unresolved_osm_geography_stays_unknown(release):
    sources, snapshot, _ = release
    path = sources / "osm_power/data.csv"
    path.write_text(path.read_text().replace(",999001,", ",,"), encoding="utf-8")
    subprocess.run(
        [
            "node",
            str(REPO / "frontend/scripts/export-public-reference.ts"),
            str(sources),
            str(snapshot),
        ],
        check=True,
        capture_output=True,
        timeout=30,
    )
    digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
    reference = PublicReference.load(snapshot, sources, expected_sha256=digest)
    assert reference.lookup("osm_power").rows[0]["lgd_code"] is None
    assert reference.lookup("osm_power", state="Synthetic State").rows == ()
    assert reference.lookup("osm_power", lgd_code=999001).rows == ()


def test_policy_comparison_never_parses_amount_or_changes_inputs(release):
    sources, snapshot, digest = release
    reference = PublicReference.load(snapshot, sources, expected_sha256=digest)
    policies = reference.lookup("state_ev_policies").rows
    rules = [
        {
            "source_url": policies[0]["source_url"],
            "amount_paise": 999,
            "effective_from": "1999-01-01",
            "conditions": "different",
        },
        {"source_url": "https://data.example.org/unmatched", "rate_bp": 100},
    ]
    before = json.dumps([policies, rules])
    findings = compare(policies, rules)
    assert findings[0]["kind"] == "source_match_requires_human_review"
    assert findings[0]["amount_comparison"] == "not_parsed; verify manually"
    assert "valid_from" in findings[0]["differences"]
    assert findings[1]["kind"] == "rule_without_policy_source_match"
    assert json.dumps([policies, rules]) == before


def test_policy_without_source_match_requires_review():
    assert compare(({"source_url": "https://data.example.org/policy"},), [])[0]["kind"] == (
        "policy_without_source_match"
    )
