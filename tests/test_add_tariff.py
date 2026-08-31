"""The add-tariff shell's pure helpers - scripts/add_tariff.py.

The planning logic is tested in test_tariff_entry.py; here we pin the file-
reading and the human-facing preview: that a well-formed row parses, that a
malformed one fails with a readable message rather than a stack trace at commit,
and that the preview echoes the money in rupees and shows the breakeven a first
tariff unlocks. No database - these helpers are deliberately DB-free.
"""

from __future__ import annotations

import datetime as dt
import json

import pytest

from app.domain.tariffs import Action, plan_insertion
from app.models.tariffs import ElectricityTariff
from scripts.add_tariff import _TEMPLATE_JSON, parse_rows, render_plan

KERALA = 32


def _raw(**over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "lgd_state_code": KERALA,
        "discom": "KSEBL",
        "consumer_category": "LT-X EV Public Charging Stations",
        "ev_specific": True,
        "energy_paise_per_kwh": 715,
        "effective_from": "2024-12-05",
        "effective_to": None,
        "order_number": "KSERC w.e.f 05.12.2024",
        "source_pdf": "https://example.org/kserc.pdf",
    }
    base.update(over)
    return base


# --- parse_rows -------------------------------------------------------------


def test_a_single_object_becomes_one_candidate() -> None:
    rows = parse_rows(_raw())
    assert len(rows) == 1
    row = rows[0]
    assert row.lgd_state_code == KERALA
    assert row.energy_paise_per_kwh == 715
    assert row.effective_from == dt.date(2024, 12, 5)
    assert row.effective_to is None


def test_a_list_becomes_many_candidates() -> None:
    rows = parse_rows([_raw(), _raw(consumer_category="HT-VI EV Charging Stations")])
    assert len(rows) == 2


def test_a_missing_required_field_is_a_readable_error() -> None:
    raw = _raw()
    del raw["source_pdf"]
    with pytest.raises(ValueError, match="source_pdf"):
        parse_rows(raw)


def test_an_unparseable_date_is_a_readable_error() -> None:
    with pytest.raises(ValueError, match="row 0"):
        parse_rows(_raw(effective_from="the fifth of December"))


def test_a_non_object_row_is_rejected() -> None:
    with pytest.raises(ValueError, match="not a JSON object"):
        parse_rows(["just a string"])


def test_the_printed_template_itself_parses() -> None:
    # The blank row the tool hands the user must be a row the tool accepts.
    rows = parse_rows(json.loads(_TEMPLATE_JSON))
    assert len(rows) == 1
    assert rows[0].ev_specific is True


# --- render_plan ------------------------------------------------------------


def _row(**over: object) -> ElectricityTariff:
    return parse_rows(_raw(**over))[0]


def test_an_insert_preview_shows_rupees_and_a_breakeven() -> None:
    plan = plan_insertion([], _row())
    assert plan.action is Action.INSERT
    text = render_plan(plan, on=dt.date(2025, 6, 1))
    assert "INSERT" in text
    # Money echoed in rupees so it can be checked against the PDF: 715p = ₹7.15.
    assert "₹7.15" in text
    # And the payoff: a concrete breakeven percentage for a default site.
    assert "sample breakeven" in text
    assert "%" in text


def test_a_refusal_preview_shows_the_reason_and_no_breakeven() -> None:
    existing = [_row(effective_from="2023-01-01", effective_to="2025-01-01")]
    plan = plan_insertion(existing, _row(effective_from="2024-06-01"))
    assert plan.action is Action.REFUSE
    text = render_plan(plan, on=dt.date(2025, 6, 1))
    assert "REFUSE" in text
    assert "resolve" in text.lower()
    assert "sample breakeven" not in text


def test_a_historical_row_preview_says_it_has_no_live_breakeven() -> None:
    # A closed row that does not govern the preview date shows no breakeven.
    plan = plan_insertion([], _row(effective_from="2020-01-01", effective_to="2021-01-01"))
    text = render_plan(plan, on=dt.date(2025, 6, 1))
    assert "historical row" in text


# --- main(), through a real (SQLite) session --------------------------------


def test_main_dry_run_reads_the_db_and_plans_a_supersession(
    tmp_path: object, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """End to end through main(): it reads the existing open order from the
    database, sees the new file supersedes it, previews that - and, being a dry
    run, writes nothing. Proves the shell's read/plan/render wiring, not just
    the pure helpers."""
    from pathlib import Path

    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import scripts.add_tariff as mod

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    ElectricityTariff.__table__.create(engine)
    make_session = sessionmaker(bind=engine)
    with make_session() as s:
        s.add(_row(effective_from="2024-12-05"))  # the current open order
        s.commit()
    monkeypatch.setattr(mod, "SessionLocal", make_session)

    path = Path(str(tmp_path)) / "rows.json"
    path.write_text(json.dumps([_raw(effective_from="2027-04-01", energy=760)]), encoding="utf-8")

    rc = mod.main(["--file", str(path)])
    out = capsys.readouterr().out

    assert rc == 0
    assert "SUPERSEDE" in out
    assert "Dry run" in out
    # A dry run must not have touched the table.
    with make_session() as s:
        assert len(s.execute(select(ElectricityTariff)).scalars().all()) == 1
