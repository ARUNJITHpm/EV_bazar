# CEA EV charging electricity consumption - source review

Dataset: `data/public/cea_ev_consumption/` (public) and table `cea_ev_consumption`
(database, migration 0024). Reviewed 2026-10-03.

## Source

- Publisher: Central Electricity Authority (CEA), Ministry of Power -
  "Electric Vehicles (EVs) Public Charging Stations (PCS) Monthly Power
  Consumption Report".
- Listing: <https://cea.nic.in/electric-vehicle-charging-reports/?lang=en>. It
  shows only the newest report; every month is reachable through the page's
  own month picker, which posts `action=monthly_archive_report`,
  `selMonthYear=YYYY-MM`, `reportType=ev_charging_rep` to
  `https://cea.nic.in/wp-admin/admin-ajax.php`.
- Archive on 2026-10-03: report months August 2022 - March 2026, none for
  April - September 2026. Publication lags the month by 2-5 months and is
  irregular (several months may appear together; September 2024 was re-issued).
- Figures are what DISCOMs report to CEA. CEA calls missing values "not
  available/reported"; they are stored as NULL, never zero.

## Licence and publication decision

CEA publishes no reuse licence. Its "Copyright Policy" link opened an
unrelated document (the Citizen Charter) on 2026-10-03, and its
[website policy](https://cea.nic.in/website-policies/?lang=en) covers linking
only. On 2026-10-03 the owner decided that publicly available government
statistics may be published on Chargeworthy Data with source attribution
(see `DATA_SOURCES_TODO.md`, "Publication rule"). The dataset's `licence`
field records that decision; it is not a CEA licence.

## What is read, and how it is checked

`app/domain/cea/parse.py` reads the PDF text (pypdf); nothing is typed by hand.

- Accepted layouts: month only (April 2024); month + year to date, three
  columns (May 2024 - November 2025); four columns, adding "other than PCS"
  (December 2025 on). Two-digit years, tables split across pages, wrapped
  names, reprinted page titles and fused footers are handled and tested
  (`tests/test_cea_ev.py`, fixtures from real reports).
- Refused: November 2024 - June 2025 (the tables are images, no text), and
  August 2022 - March 2024 (a per-DISCOM kWh layout whose DISCOM names cannot
  be tied to their rows from the text). Recovering either needs OCR or a
  table-aware extractor and a human check.
- Every report must have its state rows sum to CEA's printed Grand Total, or
  it is refused. Mismatches between a state's DISCOM rows and that state's
  line in the DISCOM table are kept as warnings: in August 2024
  (Maharashtra) and August 2025 (West Bengal) they are CEA's own
  inconsistencies between its two tables. The public file uses the state
  table only.

## Public file

`scripts/export_public_cea_ev.py --write` writes state rows (LGD names) and the
all-India total, month and year to date, from the newest file of each month.
DISCOM rows and lines spanning several states ("UT of J&K and Ladakh",
"DVC") stay in the database. Values are kWh; MU on the page is kWh / 1e6.

Known limits to state wherever it is shown:

- Coverage grows: 17 states report in mid 2024, 31-33 from 2025. A rising
  national line partly reflects more utilities reporting.
- Eight months are missing (images). They are shown as gaps, not interpolated.
- Provisional utility reporting; CEA may re-issue a month.
