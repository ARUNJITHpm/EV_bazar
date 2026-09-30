# ruff: noqa: F811, F401
"""Owner data can be erased: on request, per bill image, and by the retention purge."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.domain.owner.erasure import purge_expired
from app.models.owner import (
    OwnerAccount,
    OwnerBill,
    OwnerBillImage,
    OwnerConnectorRecord,
    OwnerForecastRecord,
    OwnerStationRecord,
)
from tests.test_owner_flow import PNG, bill, client, db, onboard, sign_in  # noqa: F401

ALL = (
    OwnerAccount,
    OwnerStationRecord,
    OwnerConnectorRecord,
    OwnerBill,
    OwnerBillImage,
    OwnerForecastRecord,
)


def counts(db: sessionmaker[Session]) -> dict[str, int]:
    with db() as s:
        return {m.__tablename__: s.query(m).count() for m in ALL}


def upload(c: TestClient) -> str:
    r = c.post("/owner/bill-images", files={"file": ("b.png", PNG, "image/png")})
    return str(r.json()["image_id"])


def test_erasing_removes_the_phone_number_and_everything_else(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    sign_in(client)
    onboard(client, bill=bill(image_id=upload(client)))
    assert all(n > 0 for n in counts(db).values())
    assert client.delete("/owner/me").status_code == 204
    assert counts(db) == dict.fromkeys(counts(db), 0)
    assert client.get("/owner/me").status_code == 401  # the session is gone with it


def test_erasing_one_account_leaves_another_alone(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    sign_in(client, "9876543210")
    onboard(client)
    client.cookies.clear()
    sign_in(client, "9123456789")
    onboard(client)
    before = counts(db)
    assert client.delete("/owner/me").status_code == 204
    after = counts(db)
    assert after["owner_accounts"] == before["owner_accounts"] - 1 == 1
    assert after["owner_stations"] == 1
    with db() as s:
        assert s.query(OwnerAccount).one().phone == "+919876543210"


def test_erasing_needs_a_session(client: TestClient) -> None:
    assert client.delete("/owner/me").status_code == 401


def test_deleting_an_image_keeps_the_confirmed_figures(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    sign_in(client)
    image = upload(client)
    sid = onboard(client, bill=bill(image_id=image))
    assert client.delete(f"/owner/bill-images/{image}").status_code == 204
    assert client.get(f"/owner/bill-images/{image}").status_code == 404
    home = client.get(f"/owner/stations/{sid}/home").json()
    assert home["last_month"]["kwh"] == 4200
    assert home["bills"][0]["image_id"] is None


def test_nobody_can_delete_someone_elses_image(client: TestClient) -> None:
    sign_in(client, "9876543210")
    image = upload(client)
    client.cookies.clear()
    sign_in(client, "9123456789")
    assert client.delete(f"/owner/bill-images/{image}").status_code == 404


def purge(db: sessionmaker[Session], **kw: int) -> tuple[int, int]:
    with db() as s:
        r = purge_expired(s, now=dt.datetime.now(dt.UTC), **kw)
        s.commit()
    return r.images_deleted, r.accounts_erased


def test_old_images_are_purged_but_the_figures_stay(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    sign_in(client)
    sid = onboard(client, bill=bill(image_id=upload(client)))
    assert purge(db, image_days=365, inactive_days=0) == (0, 0)  # fresh: kept
    with db() as s:  # age only the image, not the sign-in
        for img in s.query(OwnerBillImage):
            img.created_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=400)
        s.commit()
    assert purge(db, image_days=365, inactive_days=0) == (1, 0)
    assert counts(db)["owner_bill_images"] == 0
    assert client.get(f"/owner/stations/{sid}/home").json()["last_month"]["kwh"] == 4200


def test_inactive_accounts_are_erased_active_ones_are_not(
    client: TestClient, db: sessionmaker[Session]
) -> None:
    sign_in(client, "9876543210")
    onboard(client)
    client.cookies.clear()
    sign_in(client, "9123456789")
    onboard(client)
    with db() as s:
        old = s.query(OwnerAccount).filter_by(phone="+919876543210").one()
        old.last_login_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=800)
        s.commit()
    assert purge(db, image_days=0, inactive_days=730) == (0, 1)
    with db() as s:
        assert [a.phone for a in s.query(OwnerAccount)] == ["+919123456789"]
    assert counts(db)["owner_stations"] == 1


def test_a_limit_of_zero_switches_a_rule_off(db: sessionmaker[Session]) -> None:
    assert purge(db, image_days=0, inactive_days=0) == (0, 0)
