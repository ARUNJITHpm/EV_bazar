"""Read a CEA "EV Public Charging Stations Monthly Power Consumption Report".

The Central Electricity Authority publishes, roughly monthly and 2-5 months
late, the electricity that EV charging consumed in each state and each DISCOM:
for the report month and for the financial year to date, split into public
charging stations (excluding heavy duty), heavy-duty public stations, and EV
charging other than public stations. It is measured grid consumption as the
utilities report it - the closest public check on our own kWh estimates - not
a model output.

Pure: text in, rows out. ``pages`` is the PDF's text, one string per page, as
``pypdf`` extracts it; the fetch script owns the download and the database.

Values are stored in kWh as integers (AGENTS.md: energy in kWh). The report
prints MU (million kWh) rounded to 0.01, so each value is exact to 10,000 kWh.
"-" means the DISCOM did not report - it becomes None, never zero.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

#: The four measures per window, in the report's column order.
MEASURES = ("pcs_kwh", "heavy_duty_pcs_kwh", "other_kwh", "total_kwh")
SPANS = ("month", "fy_to_date")

#: Region headings in the state table; they group rows, they are not rows.
REGIONS = ("Northern", "Western", "Southern", "Eastern", "North Eastern")
GRAND_TOTAL = "Grand Total"

_MONTHS = {
    m: i
    for i, names in enumerate(
        (
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ),
        start=1,
    )
    for m in names
}

#: "Mar, 2026 April, 2025 to Mar, 2026" - the window line above both tables.
_WINDOW_LINE = re.compile(
    r"([A-Za-z]{3,9}),?\s*(\d{4})\s+([A-Za-z]{3,9}),?\s*(\d{4})\s+to\s+([A-Za-z]{3,9}),?\s*(\d{4})"
)
_VALUE = r"(?:-|\d+(?:\.\d+)?)"
#: A data line: optional name text, then exactly eight values.
_DATA_LINE = re.compile(rf"^(.*?)\s*((?:{_VALUE}\s+){{7}}{_VALUE})\s*$")

#: Tolerance when checking sums of figures each rounded to 0.01 MU.
_TOLERANCE_KWH = 50_000


class ReportFormatError(ValueError):
    """The PDF does not have the layout this parser was written against."""


@dataclass(frozen=True)
class ConsumptionRow:
    """One line of a table: a state, a DISCOM, or the all-India total."""

    geography: str  # "state" | "discom" | "india"
    region: str | None  # state table only
    state_name: str  # verbatim; for a DISCOM, the state it is listed under
    discom: str | None
    month: Mapping[str, int | None]  # MEASURES -> kWh
    fy_to_date: Mapping[str, int | None]


@dataclass
class Report:
    report_month: dt.date  # first day of the report month
    fy_start: dt.date  # first day of the financial year to date
    states: list[ConsumptionRow] = field(default_factory=list)
    discoms: list[ConsumptionRow] = field(default_factory=list)
    india: ConsumptionRow | None = None
    warnings: list[str] = field(default_factory=list)


def _month(name: str, year: str) -> dt.date:
    number = _MONTHS.get(name.strip().lower())
    if number is None:
        raise ReportFormatError(f"unknown month name {name!r}")
    return dt.date(int(year), number, 1)


def mu_to_kwh(raw: str) -> int | None:
    """A printed MU cell -> kWh. "-" -> None (not reported, not zero)."""
    raw = raw.strip()
    if raw == "-":
        return None
    try:
        return int(Decimal(raw) * 1_000_000)
    except InvalidOperation as exc:
        raise ReportFormatError(f"not a consumption value: {raw!r}") from exc


def _row(
    geography: str, region: str | None, state: str, discom: str | None, values: Sequence[str]
) -> ConsumptionRow:
    kwh = [mu_to_kwh(v) for v in values]
    return ConsumptionRow(
        geography=geography,
        region=region,
        state_name=state,
        discom=discom,
        month=dict(zip(MEASURES, kwh[:4], strict=True)),
        fy_to_date=dict(zip(MEASURES, kwh[4:], strict=True)),
    )


def _table_lines(page: str) -> list[str]:
    """The body lines of one table page: after the column header block.

    Every column header ends "(in MU)" - sometimes wrapped as "(in" / "MU)",
    so the marker is a line ending "MU)". Only the header has one, so the body
    starts after the last. A page with no header (a continuation page) is body
    from the top.
    """
    # Trailing spaces are kept: they tell a word break from a mid-word one.
    lines = [line.lstrip() for line in page.splitlines()]
    last = max((i for i, line in enumerate(lines) if line.rstrip().endswith("MU)")), default=-1)
    return [line for line in lines[last + 1 :] if line.strip()]


def _data_rows(lines: Sequence[str]) -> list[tuple[str, list[str]]]:
    """Join wrapped names onto their values: [(name, eight values)].

    A name may wrap over several lines before (or with) its values, e.g.
    "Dadra & Nagar" / "Haveli and Daman" / "& Diu" / "- - - - - - - -". The
    extracted text keeps a trailing space where the PDF broke between words
    ("Madhya " / "Pradesh") and none where it broke inside one ("Maharashtr" /
    "a"), so fragments are joined accordingly. Lines after the Grand Total
    (the footnote, the page number) are dropped.
    """
    rows: list[tuple[str, list[str]]] = []
    pending: list[str] = []

    def joined(last: str) -> str:
        text = "".join(f.strip() + (" " if f != f.rstrip() else "") for f in pending)
        return " ".join((text + last).split())

    for raw in lines:
        line = raw.strip()
        if line in REGIONS:
            if pending:
                raise ReportFormatError(f"name without values before region: {pending}")
            rows.append((line, []))
            continue
        match = _DATA_LINE.match(line)
        if match:
            name = joined(match.group(1))
            pending = []
            if not name:
                raise ReportFormatError(f"values without a name: {line!r}")
            rows.append((" ".join(name.split()), match.group(2).split()))
            if name == GRAND_TOTAL:
                break
        elif re.fullmatch(r"\d{1,2}", line):
            continue  # page number
        else:
            pending.append(raw)
    return rows


def _check_sum(
    report: Report, label: str, parts: Sequence[ConsumptionRow], whole: ConsumptionRow
) -> bool:
    ok = True
    for span in SPANS:
        for measure in MEASURES:
            values = [getattr(p, span)[measure] for p in parts]
            if all(v is None for v in values):
                continue
            total = sum(v for v in values if v is not None)
            expected = getattr(whole, span)[measure]
            tolerance = _TOLERANCE_KWH * max(1, len(parts))
            if expected is None or abs(total - expected) > tolerance:
                report.warnings.append(
                    f"{label}: {span} {measure} parts sum to {total} kWh, printed {expected}"
                )
                ok = False
    return ok


def parse_report(pages: Sequence[str]) -> Report:
    """The state, DISCOM and all-India rows of one report.

    Refuses (``ReportFormatError``) when the layout is not recognised or when
    the state rows do not add up to the printed Grand Total - a wrong number
    must not enter quietly. DISCOM-to-state mismatches are kept as warnings,
    because they are the source's own inconsistencies, not parsing errors.
    """
    state_page = next((i for i, p in enumerate(pages) if "State/UT wise" in p), None)
    discom_page = next((i for i, p in enumerate(pages) if "DISCOM/Utility-wise" in p), None)
    if state_page is None or discom_page is None:
        raise ReportFormatError("state or DISCOM table not found")
    window = _WINDOW_LINE.search(pages[state_page])
    if not window:
        raise ReportFormatError("report month line not found")
    report_month = _month(window.group(1), window.group(2))
    fy_start = _month(window.group(3), window.group(4))
    if _month(window.group(5), window.group(6)) != report_month:
        raise ReportFormatError("year-to-date window does not end at the report month")
    report = Report(report_month=report_month, fy_start=fy_start)

    region: str | None = None
    for name, values in _data_rows(_table_lines(pages[state_page])):
        if not values:
            region = name
        elif name == GRAND_TOTAL:
            report.india = _row("india", None, "India", None, values)
        else:
            report.states.append(_row("state", region, name, None, values))
    if report.india is None or not report.states:
        raise ReportFormatError("state table has no rows or no Grand Total")
    if not _check_sum(report, "states vs Grand Total", report.states, report.india):
        raise ReportFormatError("; ".join(report.warnings))

    # The DISCOM table lists each state, then its DISCOMs. A state line is one
    # whose name is in the state table, or a combined "UT of ..." line.
    state_names = {"".join(r.state_name.split()) for r in report.states}
    discom_lines: list[str] = []
    for page in pages[discom_page:]:
        discom_lines.extend(_table_lines(page))
        if any(line.startswith(GRAND_TOTAL) for line in discom_lines):
            break
    current: ConsumptionRow | None = None
    members: list[ConsumptionRow] = []

    def close() -> None:
        if current is not None and members:
            _check_sum(report, f"{current.state_name} DISCOMs", members, current)

    for name, values in _data_rows(discom_lines):
        if name == GRAND_TOTAL:
            break
        if "".join(name.split()) in state_names or name.startswith("UT of"):
            close()
            current = _row("state", None, name, None, values)
            members = []
        elif current is None:
            raise ReportFormatError(f"DISCOM {name!r} before any state")
        else:
            row = _row("discom", None, current.state_name, name, values)
            report.discoms.append(row)
            members.append(row)
    close()
    if not report.discoms:
        raise ReportFormatError("DISCOM table has no rows")
    return report


_ALIASES = {
    "J&K": "JAMMU & KASHMIR",
    "JAMMU AND KASHMIR": "JAMMU & KASHMIR",
    "DADRA & NAGAR HAVELI AND DAMAN & DIU": "DADRA,NAGAR HAVELI,DAMAN & DIU",
    "ANDAMAN & NICOBAR ISLANDS": "ANDAMAN & NICOBAR",
}


def lgd_state_code(name: str, states: Mapping[str, int]) -> int | None:
    """CEA's state spelling -> LGD state code, or None when it names no one state.

    ``states`` maps the LGD names ("KERALA", "JAMMU & KASHMIR") to codes. The
    DISCOM table's combined "UT of J&K and Ladakh" is two states and maps to
    None rather than to either.
    """
    key = " ".join(name.upper().replace("UT OF ", "").split())
    key = _ALIASES.get(key, key)
    return states.get(key)
