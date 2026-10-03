"""VAHAN month-wise registrations - the pure core and the scraper's table read.

No browser and no database: the table shapes below are what the dashboard's
"Month Wise" X-axis renders, and the scraper's extraction is exercised through a
stand-in driver that returns them.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest

from app.domain.vahan.monthly import (
    ALL_RTOS,
    CSV_FIELDS,
    EV_FUEL_SCOPE,
    NO_ROWS,
    MonthlyCount,
    aggregate_monthly,
    csv_row,
    is_monthly_csv,
    is_partial,
    month_number,
    parse_month_table,
    parse_monthly_csv,
)
from app.domain.vahan.parse import CSV_FIELDS as YEARLY_FIELDS
from scripts import scrape_vahan

HEADER = ["S No", "Vehicle Category", "JAN", "FEB", "MAR", "TOTAL"]
ROWS = [
    ["1", "2wn", "1,204", "980", "1,010", "3,194"],
    ["2", "LMV", "88", "-", "102", "190"],
]


def _counts(**kwargs: Any) -> list[MonthlyCount]:
    defaults: dict[str, Any] = {
        "state_code": "KL",
        "rto": "ADOOR SRTO - KL26",
        "year": 2026,
        "breakdown": "vehicle_category",
    }
    return parse_month_table(HEADER, ROWS, **{**defaults, **kwargs})


def test_month_headers_are_recognised_and_totals_are_not() -> None:
    assert [month_number(h) for h in ("JAN", "February", "Sept", "DEC.", "TOTAL", "")] == [
        1,
        2,
        9,
        12,
        None,
        None,
    ]


def test_month_table_becomes_one_count_per_label_and_month() -> None:
    counts = _counts()
    by_key = {(c.label, c.month.month): c.count for c in counts}
    assert by_key == {
        ("2WN", 1): 1204,
        ("2WN", 2): 980,
        ("2WN", 3): 1010,
        ("LMV", 1): 88,
        ("LMV", 3): 102,  # "-" is no reading, not zero
    }
    assert {c.month for c in counts} == {dt.date(2026, m, 1) for m in (1, 2, 3)}
    # the row TOTAL column is never stored
    assert sum(c.count for c in counts if c.label == "2WN") == 3194


def test_grouped_header_is_aligned_to_the_body() -> None:
    # Month names on their own header row, without S No and label cells.
    counts = parse_month_table(
        ["JAN", "FEB", "TOTAL"],
        [["1", "ATHER ENERGY LTD", "310", "295", "605"]],
        state_code="KL",
        rto=ALL_RTOS,
        year=2025,
        breakdown="maker",
    )
    assert [(c.label, c.month, c.count) for c in counts] == [
        ("ATHER ENERGY LTD", dt.date(2025, 1, 1), 310),
        ("ATHER ENERGY LTD", dt.date(2025, 2, 1), 295),
    ]


def test_grand_total_body_row_is_skipped() -> None:
    counts = parse_month_table(
        HEADER,
        [*ROWS, ["", "Grand Total", "1,292", "980", "1,112", "3,384"]],
        state_code="KL",
        rto="X",
        year=2026,
        breakdown="vehicle_category",
    )
    assert "GRAND TOTAL" not in {c.label for c in counts}


def test_table_without_month_columns_is_refused() -> None:
    # The yearly Fuel x Category table must never be read as month-wise.
    with pytest.raises(ValueError, match="no month columns"):
        parse_month_table(
            ["S No", "Fuel", "2WN", "LMV", "TOTAL"],
            [["1", "PURE EV", "5", "1", "6"]],
            state_code="KL",
            rto="X",
            year=2026,
            breakdown="vehicle_category",
        )


def test_unknown_breakdown_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown breakdown"):
        _counts(breakdown="model")


def test_csv_round_trip_drops_markers() -> None:
    counts = _counts()
    marker = MonthlyCount("KL", "EMPTY - KL99", dt.date(2026, 1, 1), "vehicle_category", NO_ROWS, 0)
    lines = [",".join(CSV_FIELDS)] + [
        ",".join(str(v) for v in csv_row(c)) for c in [*counts, marker]
    ]
    text = "\n".join(lines) + "\n"
    assert is_monthly_csv(text)
    assert parse_monthly_csv(text) == counts


def test_yearly_csv_is_not_mistaken_for_monthly() -> None:
    assert not is_monthly_csv(",".join(YEARLY_FIELDS) + "\nKL,X,2025,PURE EV,2WN,4\n")


def test_other_fuel_scope_and_mid_month_dates_are_refused() -> None:
    header = ",".join(CSV_FIELDS)
    with pytest.raises(ValueError, match="fuel scope"):
        parse_monthly_csv(f"{header}\nKL,X,2026-01-01,maker,TATA,PETROL,4\n")
    with pytest.raises(ValueError, match="first day"):
        parse_monthly_csv(f"{header}\nKL,X,2026-01-15,maker,TATA,{EV_FUEL_SCOPE},4\n")


def test_rtos_sum_into_districts_and_state_reads_stay_state_rows() -> None:
    jan = dt.date(2026, 1, 1)
    counts = [
        MonthlyCount("KL", "A - KL1", jan, "vehicle_category", "2WN", 10),
        MonthlyCount("KL", "B - KL2", jan, "vehicle_category", "2WN", 5),
        MonthlyCount("KL", "LOST - KL3", jan, "vehicle_category", "2WN", 2),
        MonthlyCount("KL", ALL_RTOS, jan, "maker", "ATHER ENERGY LTD", 40),
    ]
    placement = {("KL", "A - KL1"): (302, 32), ("KL", "B - KL2"): (302, 32)}
    slices = aggregate_monthly(counts, placement, {"KL": 32})
    rows = {(s.geography, s.lgd_district_code, s.label): (s.count, s.rto_count) for s in slices}
    assert rows == {
        ("district", 302, "2WN"): (15, 2),
        ("district", None, "2WN"): (2, 1),  # unplaced RTO keeps its state
        ("state", None, "ATHER ENERGY LTD"): (40, 1),
    }
    assert all(s.lgd_state_code == 32 for s in slices)


def test_snapshot_month_is_partial() -> None:
    snap = dt.date(2026, 10, 3)
    assert is_partial(dt.date(2026, 10, 1), snap)
    assert not is_partial(dt.date(2026, 9, 1), snap)


class _Driver:
    """Stands in for Selenium: returns rendered tables for the extraction JS."""

    def __init__(self, tables: list[dict[str, Any]]) -> None:
        self.tables = tables

    def execute_script(self, script: str, *args: Any) -> Any:
        assert script == scrape_vahan._ALL_TABLES_JS
        return self.tables


class _PagedDriver:
    """Two pages of 'next'-paginated maker rows, like the dashboard's table."""

    def __init__(self) -> None:
        head = [["S No", "Maker", "JAN", "TOTAL"]]
        self.pages = [
            {
                "heads": head,
                "rows": [["1", "ATHER ENERGY LTD", "40", "40"]],
                "id": "t",
                "more": True,
            },
            {
                "heads": head,
                "rows": [["26", "TVS MOTOR COMPANY LTD", "35", "35"]],
                "id": "t",
                "more": False,
            },
        ]
        self.page = 0

    def execute_script(self, script: str, *args: Any) -> Any:
        if script == scrape_vahan._ALL_TABLES_JS:
            return [self.pages[self.page]]
        if script == scrape_vahan._NEXT_PAGE_JS:
            assert args == ("t",)
            self.page += 1
            return True
        return True  # PrimeFaces ajax-idle probe


def test_scraper_reads_the_first_table_with_month_columns() -> None:
    driver = _Driver(
        [
            {"heads": [["S No", "Fuel", "2WN"]], "rows": [["1", "PURE EV", "3"]]},
            {
                "heads": [["S No", "Maker", "Month Wise"], ["JAN", "TOTAL"]],
                "rows": [["1", "TATA MOTORS PASSENGER VEHICLES LTD", "120", "120"]],
            },
        ]
    )
    counts = scrape_vahan.extract_monthly(driver, "TN", ALL_RTOS, "2025", "maker")
    assert counts == [
        MonthlyCount(
            "TN", ALL_RTOS, dt.date(2025, 1, 1), "maker", "TATA MOTORS PASSENGER VEHICLES LTD", 120
        )
    ]


def test_scraper_reads_every_page_of_a_paginated_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scrape_vahan.time, "sleep", lambda _s: None)
    counts = scrape_vahan.extract_monthly(_PagedDriver(), "KL", ALL_RTOS, "2025", "maker")
    assert [(c.label, c.count) for c in counts] == [
        ("ATHER ENERGY LTD", 40),
        ("TVS MOTOR COMPANY LTD", 35),
    ]


def test_scraper_returns_nothing_when_no_month_table_rendered() -> None:
    driver = _Driver([{"heads": [["S No", "Fuel"]], "rows": []}])
    assert scrape_vahan.extract_monthly(driver, "KL", "X", "2025", "maker") == []


def test_monthly_resume_keys_are_rto_and_year(tmp_path: Path) -> None:
    out = tmp_path / "monthly.csv"
    rows = [
        MonthlyCount("KL", "A - KL1", dt.date(2025, m, 1), "vehicle_category", "2WN", 1)
        for m in (1, 2)
    ]
    out.write_text(
        ",".join(CSV_FIELDS) + "\n" + "".join(",".join(map(str, csv_row(r))) + "\n" for r in rows),
        encoding="utf-8",
    )
    assert scrape_vahan.already_done_monthly(out) == {("A - KL1", "2025")}
