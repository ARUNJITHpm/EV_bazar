"""PLAN 1.6 - the tier gate's evidence derivation.

``tier_for`` (the pure gate) is pinned by test_lookup_panel; what this file
pins is ``state_tier``: the flags must come from the LIVE tables through the
same definitions the coverage panel uses - a currently-effective tariff row
(a superseded order is history, not coverage), the state's own VAHAN rows,
and the national poll_runs count.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.domain.resolution.coverage import state_tier
from app.models import Base
from app.models.charger_status import PollRun
from app.models.tariffs import ElectricityTariff
from app.models.vahan import VahanEvRegistration

KERALA, KARNATAKA = 32, 29


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(
        engine,
        tables=[
            ElectricityTariff.__table__,
            VahanEvRegistration.__table__,
            PollRun.__table__,
        ],
    )
    with Session(engine) as s:
        yield s


def _tariff(state: int, *, effective_to: dt.date | None = None) -> ElectricityTariff:
    return ElectricityTariff(
        lgd_state_code=state,
        discom="KSEB",
        consumer_category="LT EV charging",
        ev_specific=True,
        energy_paise_per_kwh=640,
        effective_from=dt.date(2024, 4, 1),
        effective_to=effective_to,
        order_number="OA-XX/2024",
        source_pdf="kserc_order.pdf",
    )


def _vahan(state: int) -> VahanEvRegistration:
    # Explicit id: SQLite does not autoincrement a BigInteger Identity PK.
    return VahanEvRegistration(
        id=1,
        lgd_district_code=565,
        lgd_state_code=state,
        snapshot_date=dt.date(2026, 8, 18),
        period="2025",
        fuel_category="PURE EV",
        vehicle_class="TOTAL",
        count=17_895,
        source_sha256="0" * 64,
    )


def test_tariff_and_vahan_without_polls_is_tier_2(session: Session) -> None:
    session.add_all([_tariff(KERALA), _vahan(KERALA)])
    session.flush()

    v = state_tier(session, KERALA)
    assert (v.tier, v.has_tariff, v.has_vahan, v.has_poll) == (2, True, True, False)
    assert "competitor occupancy" in v.why


def test_evidence_is_per_state_not_global(session: Session) -> None:
    """Kerala's tariff must not light Karnataka's flag."""
    session.add_all([_tariff(KERALA), _vahan(KERALA)])
    session.flush()

    v = state_tier(session, KARNATAKA)
    assert v.tier == 3
    assert not v.has_tariff and not v.has_vahan


def test_a_superseded_tariff_is_history_not_coverage(session: Session) -> None:
    session.add(_tariff(KERALA, effective_to=dt.date(2025, 4, 1)))
    session.flush()

    v = state_tier(session, KERALA)
    assert v.tier == 3
    assert not v.has_tariff


def test_all_three_layers_reach_tier_1(session: Session) -> None:
    session.add_all(
        [
            _tariff(KERALA),
            _vahan(KERALA),
            PollRun(
                source="tata_power_ez",
                started_at=dt.datetime(2026, 8, 20, tzinfo=dt.UTC),
                outcome="ok",
            ),
        ]
    )
    session.flush()

    assert state_tier(session, KERALA).tier == 1
