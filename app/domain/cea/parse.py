"""Read a CEA "EV Public Charging Stations Monthly Power Consumption Report".

The Central Electricity Authority publishes, roughly monthly and 2-5 months
late, the electricity that EV charging consumed in each state and each DISCOM:
for the report month and (since mid 2024) the financial year to date, split
into public charging stations (excluding heavy duty), heavy-duty public
stations, and (since late 2025) EV charging other than public stations. It is
measured grid consumption as the utilities report it - the closest public
check on our own kWh estimates - not a model output.

Pure: text in, rows out. ``pages`` is the PDF's text, one string per page, as
``pypdf`` extracts it; the fetch script owns the download and the database.

Values are stored in kWh as integers (AGENTS.md: energy in kWh). The report
prints MU (million kWh) rounded to 0.01, so each value is exact to 10,000 kWh.
"-" or "*" means the DISCOM did not report - it becomes None, never zero.

Layouts seen in the archive (August 2022 - March 2026):

  * Dec 2023 - Jul 2024: the month only, three columns.
  * Aug 2024 - Nov 2025: month and year to date, three columns each.
  * Dec 2025 onward: month and year to date, four columns each.
  * Nov 2024 - Jun 2025: the tables are images - no text, refused.
  * Aug 2022 - Jun 2023: a per-DISCOM kWh layout with station counts - refused.
"""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

#: The four measures per span, in the report's column order.
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
#: Some months print a two-digit year first ("July, 25 April, 2025 to ...").
_WINDOW_LINE = re.compile(
    r"([A-Za-z]{3,9}),?\s*(\d{2,4})\s+([A-Za-z]{3,9}),?\s*(\d{4})\s+to\s+"
    r"([A-Za-z]{3,9}),?\s*(\d{4})"
)
#: Month-only reports: "Region April, 2024".
_MONTH_ONLY_LINE = re.compile(r"Region\s+([A-Za-z]{3,9}),?\s*(\d{2,4})\b")
#: "-" and "*" both mark a value the utility did not report (2024 reports use "*").
_VALUE = r"(?:-|\*|\d+(?:\.\d+)?)"
_ENDS_IN_VALUES = re.compile(rf"(?:^|\s){_VALUE}\s+{_VALUE}\s+{_VALUE}\s*$")
#: CEA's file-number footer, up to its "/<diary no>/<year>" end.
_FOOTER = re.compile(r"^CEA-PL[-/].*?/\d{4,6}/\d{4}\s*")


def _is_row_or_region(line: str) -> bool:
    text = line.strip()
    return text in REGIONS or bool(_ENDS_IN_VALUES.search(text))


def _data_line(width: int) -> re.Pattern[str]:
    """A data line: optional name text, then exactly ``width`` values."""
    return re.compile(rf"^(.*?)\s*((?:{_VALUE}\s+){{{width - 1}}}{_VALUE})\s*$")


_THREE = ("pcs_kwh", "heavy_duty_pcs_kwh", "total_kwh")
#: Columns per span by table width, and whether a year-to-date half follows.
#: A column a layout lacks is None - not reported - never zero.
LAYOUTS: dict[int, tuple[tuple[str, ...], bool]] = {
    8: (MEASURES, True),
    6: (_THREE, True),
    3: (_THREE, False),
}

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
    fy_to_date: Mapping[str, int | None] | None  # None in a month-only report


@dataclass
class Report:
    report_month: dt.date  # first day of the report month
    fy_start: dt.date | None  # first day of the financial year; None if month-only
    states: list[ConsumptionRow] = field(default_factory=list)
    discoms: list[ConsumptionRow] = field(default_factory=list)
    india: ConsumptionRow | None = None
    warnings: list[str] = field(default_factory=list)


def _month(name: str, year: str) -> dt.date:
    number = _MONTHS.get(name.strip().lower())
    if number is None:
        raise ReportFormatError(f"unknown month name {name!r}")
    full = int(year) + (2000 if len(year) == 2 else 0)
    return dt.date(full, number, 1)


def mu_to_kwh(raw: str) -> int | None:
    """A printed MU cell -> kWh. "-" or "*" -> None (not reported, not zero)."""
    raw = raw.strip()
    if raw in {"-", "*"}:
        return None
    try:
        return int(Decimal(raw) * 1_000_000)
    except InvalidOperation as exc:
        raise ReportFormatError(f"not a consumption value: {raw!r}") from exc


def _row(
    geography: str, region: str | None, state: str, discom: str | None, values: Sequence[str]
) -> ConsumptionRow:
    kwh = [mu_to_kwh(v) for v in values]
    columns, has_year = LAYOUTS[len(values)]
    half = len(columns)

    def span(cells: Sequence[int | None]) -> dict[str, int | None]:
        found = dict(zip(columns, cells, strict=True))
        return {measure: found.get(measure) for measure in MEASURES}

    return ConsumptionRow(
        geography=geography,
        region=region,
        state_name=state,
        discom=discom,
        month=span(kwh[:half]),
        fy_to_date=span(kwh[half:]) if has_year else None,
    )


def _is_state_header(line: str) -> bool:
    return line == "State/UT"


def _is_discom_header(line: str) -> bool:
    return line == "DISCOM" or line.replace(" ", "").startswith(("State/DISCOM", "State-UT/DISCOM"))


def _segments(pages: Sequence[str]) -> dict[str, list[str]]:
    """Every page's lines, split into the state table's and the DISCOM table's.

    The tables run across page breaks and may start mid-page, so the pages are
    read as one stream. A table's column header ("State/UT", or "State-UT/" /
    "DISCOM") switches the stream to that table; the header block itself - up
    to its last line ending "MU)" before the first row - is dropped, wherever
    it repeats. Page numbers and the "CEA-PL/..." file-number footer are
    dropped too. Trailing spaces are kept: they tell a word break from a
    mid-word one (see ``_data_rows``).
    """
    lines = [
        line
        for page in pages
        for raw in page.splitlines()
        # The file-number footer ("CEA-PL/3/2022-CEA I/48891/2025",
        # "CEA-PL-14-26/11/2025-PDM Division I/64009/2026") can be fused onto
        # the next row's text, so it is cut off rather than the line dropped.
        if (line := _FOOTER.sub("", raw.lstrip())).strip()
        and not re.fullmatch(r"\d{1,2}", line.strip())
    ]
    out: dict[str, list[str]] = {"state": [], "discom": []}
    current: str | None = None
    i = 0
    while i < len(lines):
        text = lines[i].strip()
        if _is_state_header(text):
            kind: str | None = "state"
        elif _is_discom_header(text):
            kind = "discom"
        else:
            kind = None
        if kind is None:
            if current is not None:
                out[current].append(lines[i])
            i += 1
            continue
        # A repeated page title sits just above a repeated header; left in, it
        # would be read as the start of the next row's name.
        if current is not None:
            while out[current] and not _is_row_or_region(out[current][-1]):
                out[current].pop()
        current = kind
        first_row = next(
            (
                j
                for j in range(i + 1, len(lines))
                if lines[j].strip() in REGIONS or _ENDS_IN_VALUES.search(lines[j].strip())
            ),
            len(lines),
        )
        header_end = max(
            (j for j in range(i, first_row) if lines[j].rstrip().endswith("MU)")), default=i
        )
        i = header_end + 1
    return out


def _data_rows(lines: Sequence[str], width: int) -> list[tuple[str, list[str]]]:
    """Join wrapped names onto their values: [(name, ``width`` values)].

    A name may wrap over several lines before (or with) its values, e.g.
    "Dadra & Nagar" / "Haveli and Daman" / "& Diu" / "- - - - - - - -". The
    extracted text keeps a trailing space where the PDF broke between words
    ("Madhya " / "Pradesh") and none where it broke inside one ("Maharashtr" /
    "a"), so fragments are joined accordingly. Lines after the Grand Total
    (the footnote, the next table's title) are dropped.
    """
    rows: list[tuple[str, list[str]]] = []
    pending: list[str] = []
    pattern = _data_line(width)

    def joined(last: str) -> str:
        text = "".join(f.strip() + (" " if f != f.rstrip() else "") for f in pending)
        # Footnote markers ("Delhi*") are the source's annotations, not names.
        return " ".join((text + last).split()).rstrip("*").strip()

    for raw in lines:
        line = raw.strip()
        if line in REGIONS or (pending and joined(line) in REGIONS):
            # "North " / "Eastern" can wrap like any other name.
            rows.append((joined(line) if pending else line, []))
            pending = []
            continue
        match = pattern.match(line)
        if match:
            name = joined(match.group(1))
            pending = []
            if not name:
                raise ReportFormatError(f"values without a name: {line!r}")
            rows.append((name, match.group(2).split()))
            if name == GRAND_TOTAL:
                break
        else:
            pending.append(raw)
    return rows


def _check_sum(
    report: Report, label: str, parts: Sequence[ConsumptionRow], whole: ConsumptionRow
) -> bool:
    ok = True
    for span in SPANS:
        whole_span = getattr(whole, span)
        if whole_span is None:
            continue
        for measure in MEASURES:
            values = [(getattr(p, span) or {}).get(measure) for p in parts]
            if all(v is None for v in values):
                continue
            total = sum(v for v in values if v is not None)
            expected = whole_span[measure]
            tolerance = _TOLERANCE_KWH * max(1, len(parts))
            if expected is None or abs(total - expected) > tolerance:
                report.warnings.append(
                    f"{label}: {span} {measure} parts sum to {total} kWh, printed {expected}"
                )
                ok = False
    return ok


def _report_month(pages: Sequence[str], has_year: bool) -> tuple[dt.date, dt.date | None]:
    text = "\n".join(pages)
    if not has_year:
        single = _MONTH_ONLY_LINE.search(text)
        if not single:
            raise ReportFormatError("report month line not found")
        return _month(single.group(1), single.group(2)), None
    window = _WINDOW_LINE.search(text)
    if not window:
        raise ReportFormatError("report month line not found")
    report_month = _month(window.group(1), window.group(2))
    if _month(window.group(5), window.group(6)) != report_month:
        raise ReportFormatError("year-to-date window does not end at the report month")
    return report_month, _month(window.group(3), window.group(4))


def parse_report(pages: Sequence[str]) -> Report:
    """The state, DISCOM and all-India rows of one report.

    Refuses (``ReportFormatError``) when the layout is not recognised or when
    the state rows do not add up to the printed Grand Total - a wrong number
    must not enter quietly. DISCOM-to-state mismatches are kept as warnings,
    because they are the source's own inconsistencies, not parsing errors.
    """
    segments = _segments(pages)
    if not segments["state"] or not segments["discom"]:
        raise ReportFormatError("state or DISCOM table not found (or the tables are images)")
    state_text = "\n".join(line.rstrip() for line in segments["state"])
    total_line = re.search(
        rf"Grand\s+Total\s+((?:{_VALUE}[ \t]+)*{_VALUE})[ \t]*$", state_text, re.M
    )
    width = len(total_line.group(1).split()) if total_line else 0
    if width not in LAYOUTS:
        raise ReportFormatError(f"unrecognised table width {width}")
    report_month, fy_start = _report_month(pages, LAYOUTS[width][1])
    report = Report(report_month=report_month, fy_start=fy_start)

    region: str | None = None
    for name, values in _data_rows(segments["state"], width):
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
    current: ConsumptionRow | None = None
    members: list[ConsumptionRow] = []

    def close() -> None:
        if current is not None and members:
            _check_sum(report, f"{current.state_name} DISCOMs", members, current)

    for name, values in _data_rows(segments["discom"], width):
        if name == GRAND_TOTAL:
            break
        if not values:
            continue  # a region heading repeated in the DISCOM table
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
    "TAMIL NAIDU": "TAMIL NADU",  # the 2024 reports' spelling
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
