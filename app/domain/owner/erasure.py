"""Erasing owner data - the owner's right to delete, and the retention limits.

Two things leave the database here, and nothing else does:

* an owner's own request (``erase_account``): the account, its phone number, its
  stations, connectors, bills, forecasts and bill images, all of it;
* the retention purge (``purge_expired``): bill images older than the retention
  period (the confirmed figures stay - the image is only there to be checked
  against), and accounts nobody has signed in to for the inactivity period.

Rows other owners' peer averages were built from disappear with the account; the
averages are recomputed from what remains, and are hidden below 10 stations.
"""

from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.domain.owner.grid import erase_grid_for_stations
from app.models.owner import (
    OwnerAccount,
    OwnerBill,
    OwnerBillImage,
    OwnerConnectorRecord,
    OwnerForecastRecord,
    OwnerStationRecord,
)


@dataclass(frozen=True)
class PurgeResult:
    images_deleted: int
    accounts_erased: int


def erase_account(session: Session, account_id: int) -> None:
    """Delete the account and everything it holds, phone number included."""
    station_ids = list(
        session.scalars(
            select(OwnerStationRecord.id)
            .where(OwnerStationRecord.account_id == account_id)
            .order_by(OwnerStationRecord.id)
            .with_for_update()
        )
    )
    erase_grid_for_stations(session, station_ids)
    if station_ids:
        for model in (OwnerForecastRecord, OwnerBill, OwnerConnectorRecord):
            session.execute(delete(model).where(model.station_id.in_(station_ids)))
        session.execute(delete(OwnerStationRecord).where(OwnerStationRecord.id.in_(station_ids)))
    session.execute(delete(OwnerBillImage).where(OwnerBillImage.account_id == account_id))
    session.execute(delete(OwnerAccount).where(OwnerAccount.id == account_id))
    session.flush()


def delete_image(session: Session, account_id: int, image_id: uuid.UUID) -> bool:
    """Delete one bill image the account owns; its bill keeps the confirmed figures."""
    image = session.get(OwnerBillImage, image_id)
    if image is None or image.account_id != account_id:
        return False
    session.execute(update(OwnerBill).where(OwnerBill.image_id == image.id).values(image_id=None))
    session.execute(delete(OwnerBillImage).where(OwnerBillImage.id == image.id))
    session.flush()
    return True


def purge_expired(
    session: Session, *, now: dt.datetime, image_days: int, inactive_days: int
) -> PurgeResult:
    """Apply the retention limits. A limit of 0 or less switches that rule off."""
    images = 0
    if image_days > 0:
        cutoff = now - dt.timedelta(days=image_days)
        old = list(
            session.scalars(select(OwnerBillImage.id).where(OwnerBillImage.created_at < cutoff))
        )
        if old:
            session.execute(
                update(OwnerBill).where(OwnerBill.image_id.in_(old)).values(image_id=None)
            )
            session.execute(delete(OwnerBillImage).where(OwnerBillImage.id.in_(old)))
            images = len(old)
    accounts = 0
    if inactive_days > 0:
        cutoff = now - dt.timedelta(days=inactive_days)
        stale = list(
            session.scalars(
                select(OwnerAccount.id).where(
                    (OwnerAccount.last_login_at < cutoff)
                    | (OwnerAccount.last_login_at.is_(None) & (OwnerAccount.created_at < cutoff))
                )
            )
        )
        for account_id in stale:
            erase_account(session, account_id)
        accounts = len(stale)
    session.flush()
    return PurgeResult(images_deleted=images, accounts_erased=accounts)
