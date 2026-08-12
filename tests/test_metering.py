"""PART C.1 - the tests that make the cap real.

PLAN Part C exit criteria:

  * no paid call can execute without writing a usage event
  * hitting a configured cap PROVABLY refuses the call, rather than logging
    and proceeding

Runs against SQLite in-memory: the metering logic is plain SQL aggregation
with no PostGIS or JSONB-operator dependency, so it does not need Postgres
to be exercised.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import PaidProvider
from app.metering import (
    PriceCard,
    QuotaExceededError,
    billing_month,
    cost_paise,
    meter,
    quota_state,
)
from app.models import Base
from app.models.api_usage import ApiUsageEvent, UsageStatus

CARD = PriceCard(
    version="test-card-v1",
    micro_paise_per_unit_in=40_000_000,  # Rs 40 per call
    micro_paise_per_unit_out=0,
)

CAPPED = PaidProvider(api_key="k", monthly_cap=3, console_cap_confirmed=True)
UNCAPPED = PaidProvider()


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=[ApiUsageEvent.__table__])
    with Session(engine) as s:
        yield s


def events(session: Session) -> list[ApiUsageEvent]:
    return list(session.execute(select(ApiUsageEvent)).scalars())


# --- pricing ---------------------------------------------------------------


def test_cost_rounds_up_so_the_bill_is_never_understated() -> None:
    # 1.5 paise for one unit must bill as 2, not 1.
    card = PriceCard(version="v", micro_paise_per_unit_in=1_500_000)
    assert cost_paise(card, units_in=1) == 2


def test_free_allowance_is_consumed_before_anything_is_charged() -> None:
    # 1 paise per call, first 10 calls of the month free.
    card = PriceCard(version="v", micro_paise_per_unit_in=1_000_000, free_units_per_month=10)
    assert cost_paise(card, units_in=1, units_already_used_this_month=0) == 0
    assert cost_paise(card, units_in=1, units_already_used_this_month=9) == 0
    assert cost_paise(card, units_in=1, units_already_used_this_month=10) == 1


def test_llm_input_and_output_are_priced_separately() -> None:
    card = PriceCard(version="v", micro_paise_per_unit_in=30, micro_paise_per_unit_out=120)
    # 10k in, 2k out -> 300_000 + 240_000 micro-paise -> 0.54 paise -> 1
    assert cost_paise(card, units_in=10_000, units_out=2_000) == 1


def test_negative_units_are_rejected() -> None:
    with pytest.raises(ValueError, match="negative"):
        cost_paise(CARD, units_in=-1)


def test_billing_month_is_utc_first_of_month() -> None:
    # 00:30 IST on 1 Sept is still 19:00 UTC on 31 Aug - it bills to August.
    ist = dt.timezone(dt.timedelta(hours=5, minutes=30))
    assert billing_month(dt.datetime(2026, 9, 1, 0, 30, tzinfo=ist)) == dt.date(2026, 8, 1)


# --- every call writes an event -------------------------------------------


def test_successful_call_writes_one_event(session: Session) -> None:
    with meter(
        session, provider="google_maps", operation="geocode", config=UNCAPPED, card=CARD
    ) as m:
        m.record(units_in=1)

    (row,) = events(session)
    assert row.status == UsageStatus.OK.value
    assert row.units_in == 1
    assert row.cost_paise == 40
    assert row.price_card_version == "test-card-v1"


def test_a_raising_call_still_writes_an_event(session: Session) -> None:
    """Providers bill for failed requests, so the meter must record them."""
    with (
        pytest.raises(RuntimeError, match="upstream exploded"),
        meter(
            session, provider="google_maps", operation="geocode", config=UNCAPPED, card=CARD
        ) as m,
    ):
        m.record(units_in=1)
        raise RuntimeError("upstream exploded")

    (row,) = events(session)
    assert row.status == UsageStatus.ERROR.value
    assert row.error is not None and "upstream exploded" in row.error
    assert row.cost_paise == 40  # a failed call is still a charged call


def test_cache_hit_costs_nothing_but_records_the_avoided_cost(session: Session) -> None:
    """Part 1's 'median cost per address = Rs 0' has to be evidenced."""
    with meter(
        session, provider="google_maps", operation="geocode", config=UNCAPPED, card=CARD
    ) as m:
        m.record(units_in=1, status=UsageStatus.CACHE_HIT)

    (row,) = events(session)
    assert row.cost_paise == 0
    assert row.detail is not None
    assert row.detail["cost_avoided_paise"] == 40


# --- the cap refuses -------------------------------------------------------


def test_calls_are_refused_once_the_cap_is_reached(session: Session) -> None:
    for _ in range(3):  # cap is 3
        with meter(
            session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD
        ) as m:
            m.record(units_in=1)

    with (
        pytest.raises(QuotaExceededError) as excinfo,
        meter(session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD) as m,
    ):
        m.record(units_in=1)
        pytest.fail("the block must not execute once the cap is reached")

    assert excinfo.value.used == 3
    assert excinfo.value.cap == 3


def test_the_refusal_is_itself_recorded(session: Session) -> None:
    """A cap that silently swallows demand looks like a provider outage."""
    for _ in range(3):
        with meter(
            session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD
        ) as m:
            m.record(units_in=1)

    with (
        pytest.raises(QuotaExceededError),
        meter(session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD),
    ):
        pass

    capped = [e for e in events(session) if e.status == UsageStatus.CAPPED.value]
    assert len(capped) == 1
    assert capped[0].cost_paise == 0


def test_a_call_may_not_straddle_the_cap(session: Session) -> None:
    """A cap of 3 must not be crossed by the request that would make it 4."""
    with meter(session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD) as m:
        m.record(units_in=2)

    with (
        pytest.raises(QuotaExceededError),
        meter(
            session,
            provider="google_maps",
            operation="geocode",
            config=CAPPED,
            card=CARD,
            units_expected=2,
        ),
    ):
        pass


def test_cache_hits_do_not_burn_quota(session: Session) -> None:
    """Otherwise the meter throttles us for being efficient."""
    for _ in range(5):
        with meter(
            session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD
        ) as m:
            m.record(units_in=1, status=UsageStatus.CACHE_HIT)

    state = quota_state(session, "google_maps", CAPPED, billing_month(dt.datetime.now(dt.UTC)))
    assert state.used == 0
    assert state.at_cap is False


def test_quota_state_alerts_at_eighty_percent(session: Session) -> None:
    for _ in range(2):  # 2 of 3 -> 66%
        with meter(
            session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD
        ) as m:
            m.record(units_in=1)
    month = billing_month(dt.datetime.now(dt.UTC))
    assert quota_state(session, "google_maps", CAPPED, month).should_alert is False

    with meter(session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD) as m:
        m.record(units_in=1)
    state = quota_state(session, "google_maps", CAPPED, month)
    assert state.should_alert is True
    assert state.at_cap is True
    assert state.remaining == 0


def test_a_provider_with_no_cap_is_never_refused(session: Session) -> None:
    """Self-hosted Nominatim is free; it must not be throttled."""
    for _ in range(50):
        with meter(
            session, provider="nominatim", operation="geocode", config=UNCAPPED, card=CARD
        ) as m:
            m.record(units_in=1)
    month = billing_month(dt.datetime.now(dt.UTC))
    assert quota_state(session, "nominatim", UNCAPPED, month).at_cap is False


def test_quota_is_tracked_per_provider(session: Session) -> None:
    for _ in range(3):
        with meter(
            session, provider="ola_maps", operation="geocode", config=CAPPED, card=CARD
        ) as m:
            m.record(units_in=1)

    # ola is at cap; google has its own untouched window
    with meter(session, provider="google_maps", operation="geocode", config=CAPPED, card=CARD) as m:
        m.record(units_in=1)

    month = billing_month(dt.datetime.now(dt.UTC))
    assert quota_state(session, "ola_maps", CAPPED, month).at_cap is True
    assert quota_state(session, "google_maps", CAPPED, month).used == 1
