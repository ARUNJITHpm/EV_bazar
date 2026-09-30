"""Apply the owner-data retention limits (DPDP storage limitation).

    uv run python -m scripts.purge_owner_data

Deletes bill images older than OWNER_BILL_IMAGE_RETENTION_DAYS and erases
accounts with no sign-in for OWNER_INACTIVE_PURGE_DAYS. Idempotent; run daily
(deploy/start.sh does, in the background).
"""

from __future__ import annotations

import datetime as dt

from app.config import get_settings
from app.db import SessionLocal
from app.domain.owner.erasure import purge_expired


def main() -> None:
    settings = get_settings()
    with SessionLocal() as session:
        result = purge_expired(
            session,
            now=dt.datetime.now(dt.UTC),
            image_days=settings.owner_bill_image_retention_days,
            inactive_days=settings.owner_inactive_purge_days,
        )
        session.commit()
    print(
        f"bill images deleted: {result.images_deleted}; accounts erased: {result.accounts_erased}"
    )


if __name__ == "__main__":
    main()
