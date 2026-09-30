import { useId, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { Plot } from "./Plot";
import {
  chartCsv,
  chartFilters,
  citation,
  numberLabel,
  rowValue,
  selectRows,
  validateChart,
  type ChartData,
  type ChartRow,
} from "./model";

const columns = [
  "region",
  "period",
  "indicator",
  "series",
  "label",
  "value",
  "p10",
  "p90",
  "status",
  "sample_size",
] as const;
type Column = (typeof columns)[number];
const columnNames: Record<Column, string> = {
  region: "Region",
  period: "Period",
  indicator: "Indicator",
  series: "Series",
  label: "Category",
  value: "Value / P50",
  p10: "P10",
  p90: "P90",
  status: "Status",
  sample_size: "Sample size",
};
function Table({ rows, title, unit }: { rows: readonly ChartRow[]; title: string; unit: string }) {
  const [sort, setSort] = useState<{ key: Column; descending: boolean }>({
    key: "label",
    descending: false,
  });
  const sorted = [...rows].sort((a, b) => {
    const left = a[sort.key],
      right = b[sort.key];
    if (left == null) return right == null ? 0 : 1;
    if (right == null) return -1;
    return (
      (typeof left === "number" && typeof right === "number"
        ? left - right
        : String(left).localeCompare(String(right), "en-IN")) * (sort.descending ? -1 : 1)
    );
  });
  return (
    <div
      className="analytics-table-scroll"
      role="region"
      aria-label={`${title} table`}
      tabIndex={0}
    >
      <table className="analytics-chart-table">
        <caption>
          {title} — {unit}. Estimates show P10/P50/P90.
        </caption>
        <thead>
          <tr>
            {columns.map((key) => (
              <th
                scope="col"
                key={key}
                aria-sort={
                  sort.key === key ? (sort.descending ? "descending" : "ascending") : "none"
                }
              >
                <button
                  onClick={() => setSort({ key, descending: sort.key === key && !sort.descending })}
                >
                  {columnNames[key]}
                  {sort.key === key ? (sort.descending ? " ↓" : " ↑") : ""}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, index) => (
            <tr key={index}>
              {columns.map((key) => (
                <td
                  key={key}
                  className={
                    ["value", "p10", "p90", "sample_size"].includes(key)
                      ? "analytics-number analytics-numeric"
                      : undefined
                  }
                >
                  {key === "value" && row.value == null
                    ? "Not enough data yet"
                    : typeof row[key] === "number"
                      ? numberLabel(row[key] as number)
                      : (row[key] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p>No data matches this selection.</p>}
    </div>
  );
}
export function Chart({ data }: { data: ChartData }) {
  validateChart(data);
  const uid = useId();
  const location = useLocation();
  const [params, setParams] = useSearchParams();
  const filters = chartFilters(location.search, data.id);
  const rows = selectRows(data.rows, filters);
  const table = params.get(`${data.id}.view`) === "table";
  const [message, setMessage] = useState("");
  const [manualCitation, setManualCitation] = useState("");
  const change = (key: string, value: string) => {
    setParams(
      (previous) => {
        // Browser history updates before a concurrent router render commits.
        // Read the latest URL so rapid controls cannot overwrite another filter.
        // Memory/static routers have no matching browser path and use their own state.
        const next = new URLSearchParams(
          window.location.pathname === location.pathname ? window.location.search : previous,
        );
        if (value) next.set(`${data.id}.${key}`, value);
        else next.delete(`${data.id}.${key}`);
        return next;
      },
      { preventScrollReset: true },
    );
    setMessage("");
    setManualCitation("");
  };
  const url = () => `${window.location.origin}${location.pathname}${location.search}#${data.id}`;
  const accessed = () => new Date().toISOString().slice(0, 10);
  const download = (all: boolean) => {
    const blob = new Blob([chartCsv(data, all ? data.rows : rows, url(), accessed())], {
      type: "text/csv;charset=utf-8",
    });
    const href = URL.createObjectURL(blob),
      anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `${data.id}-${all ? "all" : "selection"}.csv`;
    anchor.click();
    // Delay revocation until the browser has accepted the download.
    setTimeout(() => URL.revokeObjectURL(href), 1000);
    setMessage(
      `${all ? data.rows.length : rows.length} rows downloaded with source licences and version stamps.`,
    );
  };
  const copy = async () => {
    const text = citation(data, url(), accessed());
    try {
      await navigator.clipboard.writeText(text);
      setMessage("Citation copied.");
    } catch {
      setManualCitation(text);
      setMessage("Copy the citation from the text below.");
    }
  };
  return (
    <figure id={data.id} className="analytics-chart" aria-labelledby={`${uid}-title`}>
      <h2 id={`${uid}-title`}>{data.title}</h2>
      <p>{data.subtitle}</p>
      <fieldset className="analytics-chart-filters">
        <legend>Filter this chart</legend>
        <label htmlFor={`${uid}-region`}>
          Region (state or district)
          <input
            id={`${uid}-region`}
            type="search"
            value={filters.region}
            onChange={(event) => change("region", event.target.value)}
          />
        </label>
        {(["period", "indicator"] as const).map((key) => (
          <label key={key} htmlFor={`${uid}-${key}`}>
            {key === "period" ? "Time period" : "Indicator"}
            <select
              id={`${uid}-${key}`}
              value={filters[key]}
              onChange={(event) => change(key, event.target.value)}
            >
              <option value="">All {key === "period" ? "periods" : "indicators"}</option>
              {[...new Set(data.rows.map((row) => row[key]))].sort().map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
        ))}
      </fieldset>
      {table ? (
        <Table rows={rows} title={data.title} unit={data.unit} />
      ) : (
        <>
          <Plot
            rows={rows}
            type={data.type}
            summary={`${data.summary} Selection: ${rows.length.toLocaleString("en-IN")} observations. ${rows.map((row) => `${row.label}: ${rowValue(row)}`).join("; ")}`}
          />
          <noscript>
            <Table rows={rows} title={data.title} unit={data.unit} />
          </noscript>
        </>
      )}
      <figcaption>
        <p>
          Source:{" "}
          {data.sources.map((source, index) => (
            <span key={source.url}>
              {index ? "; " : ""}
              <a href={source.url}>{source.name}</a> ({source.licence})
            </span>
          ))}
          . Last updated: <time dateTime={data.updated}>{data.updated}</time>.
        </p>
        {data.notes.map((note) => (
          <p key={note}>{note}</p>
        ))}
        {data.rows.some((row) => row.status === "estimate") && (
          <p>
            Estimates: markers show P50; bands and whiskers show P10 to P90. These are estimates,
            with uncertainty.
          </p>
        )}
        <details>
          <summary>Output versions</summary>
          <dl>
            {Object.entries(data.versions).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </details>
      </figcaption>
      <div className="analytics-chart-controls" aria-label={`${data.title} controls`}>
        <button aria-pressed={!table} onClick={() => change("view", "")}>
          Chart
        </button>
        <button aria-pressed={table} onClick={() => change("view", "table")}>
          Table
        </button>
        <button disabled={!rows.length} onClick={() => download(false)}>
          Download CSV (current selection)
        </button>
        <button disabled={!data.rows.length} onClick={() => download(true)}>
          Download CSV (all data)
        </button>
        <button onClick={() => void copy()}>Copy citation</button>
        <button disabled title="Image export will be added in Part 8">
          Save image (coming soon)
        </button>
      </div>
      <p role="status">{message}</p>
      {manualCitation && (
        <label>
          Copy citation text
          <textarea readOnly value={manualCitation} onFocus={(event) => event.target.select()} />
        </label>
      )}
    </figure>
  );
}
