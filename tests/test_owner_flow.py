"""Owner sign-in, onboarding, bills, the station home and its peer comparison.

Runs the real handlers against in-memory SQLite. Only the owner tables are
created: the rest of the schema carries PostGIS columns SQLite cannot hold, and
nothing here reads them (the pin -> state lookup is replaced with a fixed answer).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.internal import owner
from app.db import get_session
from app.models.base import Base
from app.models.owner import (
    OwnerAccount,
    OwnerBill,
    OwnerBillImage,
    OwnerConnectorRecord,
    OwnerForecastRecord,
    OwnerStationRecord,
)
from app.models.owner_grid import GRID_MODELS

TABLES = [
    m.__table__  # type: ignore[attr-defined]
    for m in (
        OwnerAccount,
        OwnerStationRecord,
        OwnerConnectorRecord,
        OwnerBillImage,
        OwnerBill,
        OwnerForecastRecord,
    )
]
TABLES.extend(m.__table__ for m in GRID_MODELS)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
LIVE = dt.date(2025, 1, 1)
PHONE = "98765 43210"
PASSWORD = "correct horse battery"


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    monkeypatch.setenv("OWNER_AUTH_LIMIT_PER_HOUR", "0")
    monkeypatch.setenv("OWNER_SUBMIT_LIMIT_PER_HOUR", "0")
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine, tables=TABLES)
    yield sessionmaker(bind=engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def client(db: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(owner.router)

    def _session() -> Iterator[Session]:
        s = db()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_session] = _session
    monkeypatch.setattr(owner, "_place", lambda *_a: ("Kerala", "Ernakulam"))
    with TestClient(app) as c:
        yield c


def sign_in(c: TestClient, phone: str = PHONE, password: str = PASSWORD) -> dict[str, Any]:
    """Sign up a new number, or log in to one that already has an account."""
    r = c.post("/owner/signup", json={"phone": phone, "password": password})
    if r.status_code == 409:
        r = c.post("/owner/login", json={"phone": phone, "password": password})
    assert r.status_code in (200, 201), r.text
    return r.json()  # type: ignore[no-any-return]


def bill(period: str = "2025-07", kwh: float = 4200, **extra: Any) -> dict[str, Any]:
    return {"confirmed": True, "period": period, "kwh": kwh, **extra}


def onboard_body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "station": {
            "name": "Marine Drive Hub",
            "address": "Marine Drive, Kochi",
            "lat": 9.98,
            "lng": 76.27,
            "went_live": "2025-01",
        },
        "connectors": [{"standard": "CCS2", "power_kw": 60}, {"standard": "CCS2", "power_kw": 60}],
        "bill": bill(),
        "meter_answer": "separate",
        "consent_aggregate": True,
    }
    body.update(over)
    return body


def onboard(c: TestClient, **over: Any) -> int:
    r = c.post("/owner/onboard", json=onboard_body(**over))
    assert r.status_code == 201, r.text
    return int(r.json()["station_id"])


# --- sign in ------------------------------------------------------------------


def test_bad_phone_is_refused(client: TestClient) -> None:
    r = client.post("/owner/signup", json={"phone": "12345", "password": PASSWORD})
    assert r.status_code == 422


def test_short_password_is_refused_and_no_account_is_made(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    r = client.post("/owner/signup", json={"phone": PHONE, "password": "short"})
    assert r.status_code == 422
    assert "8 characters" in r.json()["detail"]
    with db() as s:
        assert s.query(OwnerAccount).count() == 0


def test_signup_signs_you_in_and_starts_with_no_stations(client: TestClient) -> None:
    r = client.post("/owner/signup", json={"phone": PHONE, "password": PASSWORD})
    assert r.status_code == 201
    assert "evsite_owner" in r.cookies
    assert client.get("/owner/me").json()["station_count"] == 0


def test_signing_up_twice_with_one_number_is_refused(client: TestClient) -> None:
    sign_in(client)
    r = client.post(
        "/owner/signup", json={"phone": "+91 98765 43210", "password": "another pass 1"}
    )
    assert r.status_code == 409
    client.cookies.clear()
    # the second attempt did not replace the first password
    ok = client.post("/owner/login", json={"phone": PHONE, "password": PASSWORD})
    assert ok.status_code == 200


def test_login_with_the_right_password(client: TestClient) -> None:
    sign_in(client)
    client.cookies.clear()
    assert client.get("/owner/me").status_code == 401
    r = client.post("/owner/login", json={"phone": "9876543210", "password": PASSWORD})
    assert r.status_code == 200
    assert client.get("/owner/me").status_code == 200


def test_wrong_password_and_unknown_number_look_the_same(client: TestClient) -> None:
    sign_in(client)
    client.cookies.clear()
    wrong = client.post("/owner/login", json={"phone": PHONE, "password": "not the password"})
    unknown = client.post("/owner/login", json={"phone": "9000000001", "password": PASSWORD})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert "evsite_owner" not in wrong.cookies


def test_the_password_is_stored_hashed_never_plain(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    sign_in(client)
    with db() as s:
        stored = s.query(OwnerAccount).one().password_hash
    assert stored is not None and stored.startswith("scrypt$")
    assert PASSWORD not in stored


def test_an_account_with_no_password_cannot_log_in(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    with db() as s:
        s.add(OwnerAccount(phone="+919876543210"))
        s.commit()
    r = client.post("/owner/login", json={"phone": PHONE, "password": PASSWORD})
    assert r.status_code == 401


def test_a_number_is_locked_after_too_many_tries(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.internal import ratelimit

    monkeypatch.setenv("OWNER_AUTH_LIMIT_PER_HOUR", "1000")
    monkeypatch.setattr(ratelimit, "_phone_limiter", ratelimit.SlidingWindowLimiter(window_seconds=900.0))
    sign_in(client)
    client.cookies.clear()
    codes = [
        client.post("/owner/login", json={"phone": PHONE, "password": f"guess number {i}"})
        for i in range(ratelimit.PHONE_ATTEMPTS_PER_15_MIN + 2)
    ]
    assert codes[0].status_code == 401
    assert codes[-1].status_code == 429
    # even the right password is refused while the number is locked
    right = client.post("/owner/login", json={"phone": PHONE, "password": PASSWORD})
    assert right.status_code == 429


def test_the_browser_only_ever_sees_a_masked_number(client: TestClient) -> None:
    me = sign_in(client)
    assert me["phone_masked"].endswith("3210")
    assert "98765" not in str(me)
    assert "98765" not in client.get("/owner/me").text
    assert me["station_count"] == 0


def test_the_full_number_is_stored(client: TestClient, db: sessionmaker[Session]) -> None:
    sign_in(client)
    with db() as s:
        assert s.query(OwnerAccount).one().phone == "+919876543210"


def test_everything_else_needs_a_session(client: TestClient) -> None:
    assert client.get("/owner/me").status_code == 401
    assert client.get("/owner/stations").status_code == 401
    assert client.post("/owner/onboard", json=onboard_body()).status_code == 401
    assert client.post("/owner/bill-images", files={"file": ("b.png", PNG)}).status_code == 401


# --- onboarding and validation ----------------------------------------------------


def test_nothing_is_saved_unless_the_owner_confirmed(client: TestClient) -> None:
    sign_in(client)
    body = onboard_body(bill=bill() | {"confirmed": False})
    assert client.post("/owner/onboard", json=body).status_code == 422
    assert client.get("/owner/stations").json() == []


def test_consent_is_required(client: TestClient) -> None:
    sign_in(client)
    r = client.post("/owner/onboard", json=onboard_body(consent_aggregate=False))
    assert r.status_code == 422
    assert client.get("/owner/stations").json() == []


def test_kwh_over_the_connectors_ceiling_names_the_limit(client: TestClient) -> None:
    sign_in(client)
    r = client.post("/owner/onboard", json=onboard_body(bill=bill(kwh=100_000)))
    assert r.status_code == 422
    assert "89,280 kWh" in r.json()["detail"]
    assert client.get("/owner/stations").json() == []  # the station was not half-created


def test_first_bill_gives_a_station_home_with_a_forecast_band(client: TestClient) -> None:
    sign_in(client)
    sid = onboard(client)
    h = client.get(f"/owner/stations/{sid}/home").json()
    assert h["last_month"]["kwh"] == 4200
    assert h["last_month"]["month_of_operation"] == 7  # Jan..Jul 2025
    f = h["forecast"]
    assert f["target_month"] == "2025-08-01"
    assert f["band"]["p10_kwh"] < f["band"]["p50_kwh"] < f["band"]["p90_kwh"]
    assert f["model_version"]
    assert h["series"] == [{"month_of_operation": 7, "period": "2025-07-01", "kwh": 4200}]


def test_history_on_the_bill_fills_earlier_months(client: TestClient) -> None:
    sign_in(client)
    history = [{"period": "2025-05", "kwh": 2000}, {"period": "2025-06", "kwh": 3000}]
    sid = onboard(client, bill=bill(history=history))
    h = client.get(f"/owner/stations/{sid}/home").json()
    assert [p["kwh"] for p in h["series"]] == [2000, 3000, 4200]


def test_an_ev_tariff_settles_the_meter_question(client: TestClient) -> None:
    sign_in(client)
    sid = onboard(client, bill=bill(tariff_category="LT EV charging"), meter_answer="shared")
    h = client.get(f"/owner/stations/{sid}/home").json()
    assert h["station"]["meter_type"] == "separate"
    assert h["station"]["possibly_shared"] is False


def test_unsure_meter_flags_the_station(client: TestClient) -> None:
    sign_in(client)
    sid = onboard(client, meter_answer=None)
    h = client.get(f"/owner/stations/{sid}/home").json()
    assert h["station"]["possibly_shared"] is True


def test_only_the_last_four_of_the_consumer_number_are_kept(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    sign_in(client)
    onboard(client, bill=bill(consumer_number="1145 8890 2233"))
    with db() as s:
        row = s.query(OwnerBill).one()
        assert row.consumer_last4 == "2233"
        assert "1145" not in str(row.__dict__)


def test_money_cards_hide_when_the_bill_lacks_the_fields(client: TestClient) -> None:
    sign_in(client)
    sid = onboard(client)
    assert client.get(f"/owner/stations/{sid}/home").json()["money"] is None


def test_money_on_the_bill(client: TestClient) -> None:
    sign_in(client)
    extra = {
        "contract_demand": 200,
        "recorded_demand": 90,
        "demand_unit": "kVA",
        "power_factor": 0.92,
        "pf_effect": "penalty",
        "pf_amount_paise": 125_000,
        "tod_peak_kwh": 800,
        "tod_normal_kwh": 2400,
        "tod_offpeak_kwh": 1000,
    }
    sid = onboard(client, bill=bill(**extra))
    m = client.get(f"/owner/stations/{sid}/home").json()["money"]
    assert m["demand"]["well_above_peak"] is True
    assert m["demand"]["unit"] == "kVA"
    assert m["power_factor"]["amount_paise"] == 125_000
    assert m["time_of_day"]["peak_kwh"] == 800


# --- bills after the first, and the track record ------------------------------------


def test_track_record_compares_each_forecast_with_the_bill_that_came_in(
    client: TestClient,
) -> None:
    sign_in(client)
    sid = onboard(client)
    f = client.get(f"/owner/stations/{sid}/home").json()["forecast"]["band"]
    inside = round((f["p10_kwh"] + f["p90_kwh"]) / 2)
    assert (
        client.post(
            f"/owner/stations/{sid}/bills", json={"bill": bill("2025-08", inside)}
        ).status_code
        == 201
    )
    miss = client.post(f"/owner/stations/{sid}/bills", json={"bill": bill("2025-09", 200)})
    assert miss.status_code == 201
    h = client.get(f"/owner/stations/{sid}/home").json()
    rows = {r["target_month"]: r for r in h["track_record"]}
    assert rows["2025-08-01"]["inside_range"] is True
    assert rows["2025-08-01"]["band"]["p50_kwh"] == pytest.approx(f["p50_kwh"])  # as it was
    assert rows["2025-09-01"]["inside_range"] is False
    assert rows["2025-09-01"]["error_pct"] < -50
    assert h["last_month"]["period"] == "2025-09-01"
    assert h["forecast"]["target_month"] == "2025-10-01"


def test_a_corrected_bill_is_a_new_row_and_wins(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    sign_in(client)
    sid = onboard(client)
    client.post(f"/owner/stations/{sid}/bills", json={"bill": bill("2025-07", 5000)})
    h = client.get(f"/owner/stations/{sid}/home").json()
    assert h["last_month"]["kwh"] == 5000
    with db() as s:
        assert s.query(OwnerBill).count() == 2


def test_a_bill_before_go_live_is_refused(client: TestClient) -> None:
    sign_in(client)
    sid = onboard(client)
    r = client.post(f"/owner/stations/{sid}/bills", json={"bill": bill("2024-11", 100)})
    assert r.status_code == 422


def test_someone_elses_station_is_not_found(client: TestClient) -> None:
    sign_in(client, "9876543210")
    sid = onboard(client)
    client.cookies.clear()
    sign_in(client, "9123456789")
    assert client.get(f"/owner/stations/{sid}/home").status_code == 404
    assert client.post(f"/owner/stations/{sid}/bills", json={"bill": bill()}).status_code == 404
    assert client.get("/owner/stations").json() == []


# --- the bill image -----------------------------------------------------------------


def test_the_image_is_kept_and_served_back(client: TestClient, db: sessionmaker[Session]) -> None:
    sign_in(client)
    r = client.post("/owner/bill-images", files={"file": ("bill.png", PNG, "image/png")})
    assert r.status_code == 201
    out = r.json()
    assert out["content_type"] == "image/png"
    assert out["suggested"] == {}  # the manual extractor proposes nothing
    got = client.get(f"/owner/bill-images/{out['image_id']}")
    assert got.content == PNG
    assert got.headers["x-content-type-options"] == "nosniff"
    sid = onboard(client, bill=bill(image_id=out["image_id"]))
    h = client.get(f"/owner/stations/{sid}/home").json()
    assert h["bills"][0]["image_id"] == out["image_id"]
    with db() as s:
        assert s.query(OwnerBillImage).count() == 1


def test_a_file_that_is_not_a_bill_is_refused(client: TestClient) -> None:
    sign_in(client)
    r = client.post("/owner/bill-images", files={"file": ("x.exe", b"MZ\x90\x00", "image/png")})
    assert r.status_code == 415


def test_another_owner_cannot_read_or_attach_an_image(client: TestClient) -> None:
    sign_in(client, "9876543210")
    img = client.post("/owner/bill-images", files={"file": ("b.png", PNG)}).json()["image_id"]
    client.cookies.clear()
    sign_in(client, "9123456789")
    assert client.get(f"/owner/bill-images/{img}").status_code == 404
    r = client.post("/owner/onboard", json=onboard_body(bill=bill(image_id=img)))
    assert r.status_code == 422


# --- peers: the ten-station threshold and the shared-meter exclusion --------------------


def seed_peers(
    db: sessionmaker[Session], n: int, *, meter: str = "separate", first: int = 100
) -> None:
    with db() as s:
        for i in range(n):
            acct = OwnerAccount(phone=f"+9190000{first + i:05d}")
            s.add(acct)
            s.flush()
            st = OwnerStationRecord(
                account_id=acct.id,
                name=f"Peer {first + i}",
                lat=10.0,
                lng=76.0,
                state_name="Kerala",
                district_name="Thrissur",
                went_live=LIVE,
                meter_type=meter,
                consent_aggregate=True,
            )
            s.add(st)
            s.flush()
            s.add(OwnerConnectorRecord(station_id=st.id, standard="CCS2", power_kw=60))
            s.add(
                OwnerBill(
                    station_id=st.id,
                    period=dt.date(2025, 7, 1),
                    kwh=1500 + 100 * i,
                    source="typed",
                )
            )
        s.commit()


def test_nine_peers_are_not_enough_and_the_page_says_so(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    seed_peers(db, 9)
    sign_in(client)
    sid = onboard(client)
    peer = client.get(f"/owner/stations/{sid}/home").json()["peer"]
    assert peer["available"] is False
    assert peer["reason"] == "too_few"
    assert peer["n"] == 9
    assert peer["percentile"] is None and peer["latest_band"] is None and peer["band"] == []
    assert "Not enough similar stations yet" in peer["message"]
    assert len(peer["model_curve"]) > 0  # the labelled model estimate stands in


def test_ten_peers_show_the_comparison_with_the_sample_size(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    seed_peers(db, 10)
    sign_in(client)
    sid = onboard(client)
    peer = client.get(f"/owner/stations/{sid}/home").json()["peer"]
    assert peer["available"] is True
    assert peer["n"] == 10
    assert "10 similar stations" in peer["message"]
    assert peer["percentile"] is not None
    assert peer["latest_band"]["p10_kwh"] < peer["latest_band"]["p90_kwh"]
    assert peer["model_curve"] == []


def test_shared_meter_stations_are_left_out_of_peer_averages(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    seed_peers(db, 9)
    seed_peers(db, 3, meter="shared", first=500)
    seed_peers(db, 2, meter="unsure", first=600)
    sign_in(client)
    sid = onboard(client)
    peer = client.get(f"/owner/stations/{sid}/home").json()["peer"]
    assert peer["available"] is False
    assert peer["n"] == 9  # the five shared/unsure stations are not counted
    seed_peers(db, 1, first=700)
    peer = client.get(f"/owner/stations/{sid}/home").json()["peer"]
    assert peer["available"] is True and peer["n"] == 10


def test_a_shared_meter_owner_is_not_compared_at_all(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    seed_peers(db, 12)
    sign_in(client)
    sid = onboard(client, meter_answer="shared")
    h = client.get(f"/owner/stations/{sid}/home").json()
    assert h["station"]["possibly_shared"] is True
    assert h["peer"]["available"] is False
    assert h["peer"]["reason"] == "shared_meter"
    assert h["peer"]["percentile"] is None


def test_a_station_is_never_its_own_peer(client: TestClient, db: sessionmaker[Session]) -> None:
    seed_peers(db, 9)
    sign_in(client)
    sid = onboard(client)
    # The cohort is other stations: 9 seeded + the owner's second = 10, not 11.
    onboard(client)
    peer = client.get(f"/owner/stations/{sid}/home").json()["peer"]
    assert peer["n"] == 10


def test_portfolio_lists_each_station_with_change_and_position(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    seed_peers(db, 10)
    sign_in(client)
    sid = onboard(client)
    client.post(f"/owner/stations/{sid}/bills", json={"bill": bill("2025-08", 5040)})
    onboard(client, station=onboard_body()["station"] | {"name": "Second Hub"})
    rows = {r["name"]: r for r in client.get("/owner/stations").json()}
    assert set(rows) == {"Marine Drive Hub", "Second Hub"}
    first = rows["Marine Drive Hub"]
    assert first["last_kwh"] == 5040
    assert first["change_pct"] == pytest.approx(20.0)  # 4200 -> 5040
    assert first["peer_n"] >= 0
    assert rows["Second Hub"]["change_pct"] is None
