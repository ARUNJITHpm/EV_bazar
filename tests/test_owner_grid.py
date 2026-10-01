"""Private revisions, null handling and erasure through the real owner API."""

import datetime as dt
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from app.domain.owner.area import area_context
from app.domain.owner.erasure import purge_expired
from app.domain.owner.grid import GridDetailsIn, OutageIn
from app.models.owner import OwnerAccount, OwnerBill, OwnerStationRecord
from app.models.owner_grid import GRID_MODELS, OwnerGridRevision
from tests.test_owner_flow import onboard, sign_in

pytest_plugins = ["tests.test_owner_flow"]


@pytest.fixture(autouse=True)
def reviewed_station(monkeypatch):
    monkeypatch.setenv("OWNER_GRID_VERIFIED_STATIONS", '{"1":"test-only-reviewed-bill"}')


def setup_station(client):
    sign_in(client)
    return onboard(client)


def grid_body(**changes):
    return {"consent_private": True, "effective_on": "2025-07-01", **changes}


def test_private_revisions_and_conflict_leave_history_unchanged(client, db):
    station = setup_station(client)
    url = f"/owner/stations/{station}/grid"
    empty = client.get(url)
    assert empty.headers["cache-control"] == "no-store"
    assert empty.json()["details"] is None
    assert len(empty.json()["versions"]) == 6
    first = client.post(url, json=grid_body(sanctioned_load_kva=0, connected_load_kw=60))
    assert first.status_code == 200
    old = first.json()["details"]
    assert old["sanctioned_load_kva"] == 0
    assert old["transformer_rating_kva"] is None
    assert old["recorded_at"].endswith("Z")
    assert client.post(url, json=grid_body(connected_load_kw=90)).status_code == 409
    second = client.post(url, json=grid_body(expected_revision_id=old["id"], connected_load_kw=90))
    assert second.json()["details"]["supersedes_id"] == old["id"]
    with db() as session:
        rows = session.scalars(select(OwnerGridRevision).order_by(OwnerGridRevision.id)).all()
        assert len(rows) == 2
        assert rows[0].connected_load_kw == 60


@pytest.mark.parametrize(
    "changes",
    [
        {"consent_private": False},
        {"sanctioned_load_kva": -1},
        {"connected_load_kw": "NaN"},
        {"effective_on": "2999-01-01"},
        {"transformer_rating_kva": 0},
        {"unexpected": 1},
    ],
)
def test_invalid_private_input_refused(client, changes):
    station = setup_station(client)
    assert (
        client.post(f"/owner/stations/{station}/grid", json=grid_body(**changes)).status_code == 422
    )


def test_outage_calendar_null_zero_corrections_and_withdrawal(client, db):
    station = setup_station(client)
    base = f"/owner/stations/{station}"
    client.post(base + "/grid", json=grid_body())
    body = {"consent_private": True, "month": "2025-02-01", "approximate_hours": 0}
    first = client.post(base + "/outages", json=body)
    assert first.status_code == 200
    previous = first.json()["outages"][0]
    assert previous["approximate_hours"] == 0
    body.update(expected_revision_id=previous["id"], approximate_hours=None)
    corrected = client.post(base + "/outages", json=body).json()["outages"][0]
    assert corrected["supersedes_id"] == previous["id"]
    assert corrected["approximate_hours"] is None
    body["approximate_hours"] = 673
    assert client.post(base + "/outages", json=body).status_code == 422
    result = client.delete(base + "/grid")
    assert result.status_code == 204
    assert result.headers["cache-control"] == "no-store"
    with db() as session:
        assert all(session.query(model).count() == 0 for model in GRID_MODELS)
        assert session.query(OwnerStationRecord).count() == 1
        assert session.query(OwnerBill).count() == 1
    assert client.get(base + "/grid").json()["outages"] == []
    assert client.post(base + "/grid", json=grid_body()).status_code == 200


def test_other_owner_cannot_read_write_or_erase_grid(client, db):
    station = setup_station(client)
    url = f"/owner/stations/{station}/grid"
    client.post(url, json=grid_body(connected_load_kw=60))
    client.cookies.clear()
    assert client.get(url).status_code == 401
    sign_in(client, phone="9876543211")
    for response in (
        client.get(url),
        client.post(url, json=grid_body()),
        client.delete(url),
        client.get(f"/owner/stations/{station}/area"),
    ):
        assert response.status_code == 404
    with db() as session:
        assert session.query(OwnerGridRevision).count() == 1


@pytest.mark.parametrize("method", ["account", "inactivity"])
def test_account_and_retention_erasure_include_every_grid_version(client, db, method):
    station = setup_station(client)
    url = f"/owner/stations/{station}/grid"
    first = client.post(url, json=grid_body()).json()["details"]
    client.post(url, json=grid_body(expected_revision_id=first["id"], connected_load_kw=10))
    if method == "account":
        assert client.delete("/owner/me").status_code == 204
    else:
        with db() as session:
            account = session.scalar(select(OwnerAccount))
            account.last_login_at = dt.datetime(2020, 1, 1, tzinfo=dt.UTC)
            session.commit()
            assert (
                purge_expired(
                    session,
                    now=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
                    image_days=0,
                    inactive_days=365,
                ).accounts_erased
                == 1
            )
            session.commit()
    with db() as session:
        assert all(session.query(model).count() == 0 for model in GRID_MODELS)


def test_area_missing_is_null_and_private_grid_does_not_change_area(client, db, monkeypatch):
    monkeypatch.setattr("app.domain.owner.area.load_report_reference", lambda: None)
    station = setup_station(client)
    url = f"/owner/stations/{station}/area"
    before = client.get(url)
    assert before.headers["cache-control"] == "no-store"
    assert len(before.json()["items"]) == 6
    assert all(item["value"] is None for item in before.json()["items"])
    client.post(f"/owner/stations/{station}/grid", json=grid_body(sanctioned_load_kva=123))
    assert client.get(url).json() == before.json()


def test_supply_uses_state_area_scope_and_never_creates_outages(client, db):
    station = setup_station(client)
    row = {
        "lgd_code": None,
        "discom_id": None,
        "period_end": "2021-03-31",
        "area_type": "rural",
        "avg_supply_hours_per_day": 20.5,
        "published_period_label": "2020-21",
        "supply_definition": "annual feeder average",
    }
    result = SimpleNamespace(
        snapshot_sha256="a" * 64,
        provenance={
            "source_name": "Reviewed source",
            "source_url": "https://example.org/source",
            "retrieved_on": "2021-04-30",
            "time_coverage": "2020-21",
        },
        rows=[row],
    )
    reference = SimpleNamespace(lookup=lambda *args, **kwargs: result)
    with db() as session:
        account = session.scalar(select(OwnerAccount))
        value = area_context(session, account.id, station, reference).items[4]
        assert "20.5 h/day" in value.value
        assert value.scope == "Kerala state area average"
        result.rows = [{**row, "discom_id": "unverified"}]
        assert area_context(session, account.id, station, reference).items[4].value is None
        result.rows = [row, row]
        assert area_context(session, account.id, station, reference).items[4].value is None
        result.rows = [row]
        session.get(OwnerStationRecord, station).state_name = None
        assert area_context(session, account.id, station, reference).items[4].value is None


def test_finite_and_calendar_validation():
    with pytest.raises(ValidationError):
        GridDetailsIn(**grid_body(connected_load_kw=float("inf")))
    with pytest.raises(ValidationError):
        OutageIn(consent_private=True, month="2025-02-02", approximate_hours=0)


def test_unreviewed_station_blocks_collection_but_allows_withdrawal(client, monkeypatch):
    station = setup_station(client)
    monkeypatch.delenv("OWNER_GRID_VERIFIED_STATIONS", raising=False)
    url = f"/owner/stations/{station}/grid"
    assert client.get(url).json()["storage_available"] is False
    blocked = client.post(url, json=grid_body())
    assert blocked.status_code == 403
    assert blocked.headers["cache-control"] == "no-store"
    invalid = client.post(url, json=grid_body(connected_load_kw=-1))
    assert invalid.status_code == 422
    assert invalid.headers["cache-control"] == "no-store"
    assert client.delete(url).status_code == 204
