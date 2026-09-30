# Shared analytics charts

Use `Chart` from `frontend/src/features/analytics/chart/Chart.tsx` within the
existing router. Its `ChartData` contract requires an explicit unit, sourced
update date, source URLs/licences, notes, summary and all six output versions.
Use `renderer_version: analytics_svg_v1`. Source observations may be scalar;
estimates must carry ordered P10/P50/P90. No model runs are part of this UI.

Rows are presentation records from approved public artifacts, not private
records. `value` means an observation or the estimate's P50. Missing/suppressed
rows carry `value: null` and no bounds or sample size. Include explicit null
rows for absent periods so line charts break at the correct category. The
publisher must enforce Part 5's privacy gates before passing any aggregate.

Each series/category label pair must be unique. Distinguish regions and
indicators in series labels, and keep every indicator in one chart in the same
unit. Prepare rows in chronological/category order; no monthly observations
are inferred from annual totals. Use at most three series in a single plot;
use small multiples for more. Small multiples share a numeric scale. Markers
and line styles distinguish series independently of colour. The SVG is static
and also renders during prerendering, with a full table inside `noscript`.

Recharts 2.15 is already installed and supports SVG chart families. This
component uses a shared deterministic SVG scale/axis implementation to keep
build-time HTML complete, including explicit gaps and range labels, without
container measurement or an additional dependency. No transitions run.

URL keys are namespaced by stable chart ID: `<id>.region`, `<id>.period`,
`<id>.indicator`, `<id>.view`. Region search matches the row's state/district
text; period and indicator are exact selections. Other query keys survive.
Rapid browser controls read the latest history URL before changing a key so
concurrent router renders cannot overwrite earlier filters. Reload and back
restore the view. JavaScript enhances filters, sorting and downloads; static
HTML preserves the default chart and complete data table.

Current-selection CSV and the plot/table use the same selected rows. All-data
CSV contains the entire approved chart input, irrespective of filters and table
sort. Both retain raw numeric values, blank missing cells, P10/P90, status,
sample size, units, source URLs, source-specific licences, update date, citation
and six versions. Text formula prefixes are neutralised for spreadsheet use;
quoted fields, newlines and UTF-8 are preserved. Original chart content is
CC BY 4.0; citations do not relicense source data. Clipboard failure provides
selectable citation text. Save image stays disabled until Part 8.

Development demo: `/data/chart-demo?fixtures=1` on `npm run dev`. It covers line,
vertical/horizontal bars, dot/range and small multiples using authored fixtures
with a visible Test data banner. Without the flag, or in a production build,
the route is unavailable. The module and fixture strings are eliminated from
production JS and source maps. No real chart is published until its input is
verified.

Acceptance: component tests, `npm run build`, `npm run data:check-build`, and
`python scripts/check_analytics_charts.py --dev-url <vite-dev> --url <preview>`.
The browser check exercises actual downloads, reload/back, keyboard controls,
375/768/1440px widths and production exclusion with JavaScript on and off.
