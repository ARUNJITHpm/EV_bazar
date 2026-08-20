"""The Progress console panel - PART C.

``build_milestones`` is pure prose over ``Signals``, and the thing worth
pinning is that its statuses follow the database rather than the author's
optimism: an empty ``poll_runs`` must read as the queue's first item, and a
non-empty one must not.
"""

from __future__ import annotations

from app.api.internal.progress import (
    InputStatus,
    Signals,
    Status,
    build_inputs,
    build_milestones,
)
from app.config import Settings

EMPTY_WORLD = Signals(
    districts=783,
    pincodes=19_312,
    crosswalk_unverified=40,
    geocoded=0,
    queue_open=0,
    sites=0,
    poll_runs=0,
    price_cards=3,
    usage_events=0,
    tariff_rows=0,
    tariff_states=0,
    competitor_stations=0,
    vahan_rows=0,
    vahan_states=0,
    predictions=0,
    reports=0,
    pin_leads=0,
    tiered_sites=0,
    sources_authorised=0,
    sources_total=8,
)


def test_typed_tariffs_move_the_milestone_off_the_queue() -> None:
    import dataclasses

    live = dataclasses.replace(EMPTY_WORLD, tariff_rows=4, tariff_states=1)
    tariffs = next(m for m in build_milestones(live) if m.part == "0.2 → 3.1")
    assert tariffs.status is Status.PARTIAL
    assert "1 state(s)" in tariffs.evidence


def test_a_stored_report_moves_the_pipeline_off_code_done() -> None:
    """The report pipeline may only claim to be live when a `reports` row can
    testify - and an empty table must read as code_done, never as done."""
    import dataclasses

    empty = next(m for m in build_milestones(EMPTY_WORLD) if m.part == "5 + 6")
    assert empty.status is Status.CODE_DONE

    live = dataclasses.replace(EMPTY_WORLD, reports=1, predictions=3)
    report = next(m for m in build_milestones(live) if m.part == "5 + 6")
    assert report.status is Status.PARTIAL
    assert "1 report(s) stored" in report.evidence

    demand = next(m for m in build_milestones(live) if m.part == "4.2")
    assert demand.status is Status.PARTIAL
    assert "3 prediction(s)" in demand.evidence


def test_a_customer_pin_moves_assess_off_code_done() -> None:
    """The funnel's front door sits right behind the poller in the queue, and
    only a customer's own pin - a sites row with geocode_source='pin' - may
    move it off code_done. Operator-made sites must not."""
    import dataclasses

    milestones = build_milestones(EMPTY_WORLD)
    assert milestones[1].part == "G.2"
    assert milestones[1].status is Status.CODE_DONE

    live = dataclasses.replace(EMPTY_WORLD, sites=5, pin_leads=2)
    assess = next(m for m in build_milestones(live) if m.part == "G.2")
    assert assess.status is Status.PARTIAL
    assert "2 customer pin(s)" in assess.evidence

    operator_only = dataclasses.replace(EMPTY_WORLD, sites=5, pin_leads=0)
    assess = next(m for m in build_milestones(operator_only) if m.part == "G.2")
    assert assess.status is Status.CODE_DONE


def test_a_stamped_site_moves_the_tier_gate_off_code_done() -> None:
    """1.6 is built; only a sites row carrying a data_tier stamp may claim it
    is live - the same row-count discipline as every other milestone."""
    import dataclasses

    built = next(m for m in build_milestones(EMPTY_WORLD) if m.part == "1.6")
    assert built.status is Status.CODE_DONE

    live = dataclasses.replace(EMPTY_WORLD, tiered_sites=3, tariff_states=2)
    gate = next(m for m in build_milestones(live) if m.part == "1.6")
    assert gate.status is Status.PARTIAL
    assert "3 site(s)" in gate.evidence
    assert "2 state(s)" in gate.evidence


def test_a_silent_poller_is_the_first_item_in_the_queue() -> None:
    first = build_milestones(EMPTY_WORLD)[0]
    assert first.part == "0.1"
    assert first.status is Status.NEXT
    assert first.to_close is not None


def test_a_running_poller_leaves_the_queue() -> None:
    import dataclasses

    live = dataclasses.replace(EMPTY_WORLD, poll_runs=1_000, sources_authorised=1)
    first = build_milestones(live)[0]
    assert first.status is Status.PARTIAL
    assert first.to_close is None
    assert "1,000" in first.evidence


def test_nothing_unfinished_is_missing_its_way_out() -> None:
    """An item that says 'not done' without saying what closes it is a
    complaint, not a milestone. DONE items may omit it."""
    for m in build_milestones(EMPTY_WORLD):
        if m.status in (Status.NEXT, Status.PARKED, Status.NOT_STARTED):
            assert m.to_close, f"{m.part} has no to_close"


def test_live_counts_appear_in_the_prose() -> None:
    by_part = {m.part: m for m in build_milestones(EMPTY_WORLD)}
    assert "783" in by_part["1.1–1.2"].evidence
    assert "19,312" in by_part["1.1–1.2"].evidence
    assert "40" in by_part["1.1–1.2"].evidence


def test_order_is_dense_and_starts_at_one() -> None:
    orders = [m.order for m in build_milestones(EMPTY_WORLD)]
    assert orders == list(range(1, len(orders) + 1))


# --- the keys-and-inputs inventory -------------------------------------------


def _bare_settings(**kwargs: object) -> Settings:
    """Settings that see only what the test passes - never the developer's .env."""
    return Settings(env="test", _env_file=None, **kwargs)  # type: ignore[arg-type]


def test_the_localhost_nominatim_default_reads_as_needing_attention() -> None:
    """The default points at a server that is not running - the page must say
    so rather than showing a green 'configured'."""
    inputs = {i.name: i for i in build_inputs(_bare_settings(), urban_layer_loaded=False)}
    nominatim = next(v for k, v in inputs.items() if "Nominatim" in k)
    assert nominatim.status is InputStatus.ATTENTION
    assert "localhost" in nominatim.detail


def test_a_pointed_nominatim_reads_as_configured() -> None:
    settings = _bare_settings(nominatim_url="https://nominatim.openstreetmap.org")
    inputs = build_inputs(settings, urban_layer_loaded=False)
    nominatim = next(i for i in inputs if "Nominatim" in i.name)
    assert nominatim.status is InputStatus.CONFIGURED


def test_a_missing_paid_key_lists_all_three_env_lines() -> None:
    """Pasting the key alone will not boot (cap-before-boot); the page must
    hand over all three lines together."""
    inputs = build_inputs(_bare_settings(), urban_layer_loaded=False)
    google = next(i for i in inputs if "Google" in i.name)
    assert google.status is InputStatus.MISSING
    joined = " ".join(google.env_vars)
    assert "GOOGLE_MAPS__API_KEY" in joined
    assert "GOOGLE_MAPS__MONTHLY_CAP" in joined
    assert "GOOGLE_MAPS__CONSOLE_CAP_CONFIRMED" in joined


def test_a_configured_paid_key_flips_on_its_own() -> None:
    settings = _bare_settings(
        google_maps={"api_key": "k", "monthly_cap": 10_000, "console_cap_confirmed": True}
    )
    inputs = build_inputs(settings, urban_layer_loaded=False)
    google = next(i for i in inputs if "Google" in i.name)
    assert google.status is InputStatus.CONFIGURED
    assert "10,000" in google.detail


def test_a_configured_but_unauthorised_cpo_endpoint_is_flagged_not_green() -> None:
    """Config alone is never consent - an endpoint without the sources.py
    authorisation must read as a problem, not as done."""
    settings = _bare_settings(chargemod={"base_url": "https://api.chargemod.example"})
    inputs = build_inputs(settings, urban_layer_loaded=False)
    chargemod = next(i for i in inputs if i.name.startswith("chargemod"))
    assert chargemod.status is InputStatus.ATTENTION
    assert "not authorised" in chargemod.detail.lower()


def test_every_scraped_source_appears_in_the_inventory() -> None:
    inputs = build_inputs(_bare_settings(), urban_layer_loaded=False)
    names = {i.name for i in inputs}
    for source in ("chargemod", "chargezone", "statiq", "kazam", "tata_power_ez"):
        assert f"{source} endpoint (poller)" in names


def test_later_items_say_not_to_chase_them() -> None:
    inputs = build_inputs(_bare_settings(), urban_layer_loaded=False)
    llm = next(i for i in inputs if "LLM" in i.name)
    assert llm.status is InputStatus.LATER
