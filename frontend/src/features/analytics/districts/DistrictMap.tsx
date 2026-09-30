import { useId, useState } from "react";
import { Link } from "react-router-dom";
import catalogue from "virtual:analytics-public-data";
import type { District } from "../data/schemas";
import { chartCsv, numberLabel, type ChartData } from "../chart/model";
import {
  districtValue,
  indicatorLabels,
  type Atlas,
  type DistrictShape,
  type DistrictValue,
  type Indicator,
} from "./model";

export function shapePaths(shapes: DistrictShape[]) {
  const points = shapes.flatMap((shape) => shape.rings.flat());
  const xs = points.map((point) => point[0] * Math.cos((25 * Math.PI) / 180)),
    ys = points.map((point) => -point[1]);
  const xmin = xs.reduce((a, b) => Math.min(a, b), Infinity),
    xmax = xs.reduce((a, b) => Math.max(a, b), -Infinity),
    ymin = ys.reduce((a, b) => Math.min(a, b), Infinity),
    ymax = ys.reduce((a, b) => Math.max(a, b), -Infinity);
  const scale = Math.min(600 / (xmax - xmin || 1), 440 / (ymax - ymin || 1));
  const xoffset = (640 - (xmax - xmin) * scale) / 2,
    yoffset = (480 - (ymax - ymin) * scale) / 2;
  return shapes.map((shape) => ({
    code: shape.lgd_code,
    path: shape.rings
      .map(
        (ring) =>
          "M" +
          ring
            .map(
              ([x, y]) =>
                `${((x * Math.cos((25 * Math.PI) / 180) - xmin) * scale + xoffset).toFixed(2)},${((-y - ymin) * scale + yoffset).toFixed(2)}`,
            )
            .join(" L") +
          " Z",
      )
      .join(" "),
  }));
}
export const mapValueLabel = (value: DistrictValue) =>
  value.value == null
    ? "Not enough data yet"
    : value.p10 != null && value.p90 != null
      ? `Estimate: ${numberLabel(value.value)} (P10 ${numberLabel(value.p10)}–P90 ${numberLabel(value.p90)}); ${value.sample_size ?? "unknown"} stations with data`
      : numberLabel(value.value);
export function DistrictMap({
  atlas,
  districts,
  initialIndicator = "registrations",
  values,
}: {
  atlas: Atlas;
  districts: District[];
  initialIndicator?: Indicator;
  values?: Partial<Record<Indicator, Record<number, DistrictValue>>>;
}) {
  const uid = useId(),
    [indicator, setIndicator] = useState<Indicator>(initialIndicator),
    [query, setQuery] = useState(""),
    [selected, setSelected] = useState<number | null>(null),
    [descending, setDescending] = useState(false),
    [sort, setSort] = useState<"district" | "value">("district");
  const get = (code: number) =>
    values?.[indicator]?.[code] ?? districtValue(atlas, code, indicator);
  const filtered = districts.filter((district) =>
    `${district.district_name} ${district.state_name}`.toLowerCase().includes(query.toLowerCase()),
  );
  const rows = [...filtered].sort((a, b) => {
    if (sort === "district")
      return a.district_name.localeCompare(b.district_name, "en-IN") * (descending ? -1 : 1);
    const left = get(a.lgd_code).value,
      right = get(b.lgd_code).value;
    return left == null
      ? right == null
        ? 0
        : 1
      : right == null
        ? -1
        : (left - right) * (descending ? -1 : 1);
  });
  const numbers = districts.flatMap((district) =>
    get(district.lgd_code).value == null ? [] : [get(district.lgd_code).value!],
  );
  const max = numbers.reduce((a, b) => Math.max(a, b), 0),
    breaks = Array.from({ length: 6 }, (_, index) => (max * index) / 5);
  const current = districts.find((district) => district.lgd_code === selected);
  const paths = shapePaths(atlas.shapes);
  const download = (all: boolean) => {
    const sources = catalogue.datasets.filter((dataset) =>
      [
        "district_reference",
        "district_boundaries",
        ...(indicator === "registrations" || indicator === "ratio" ? ["ev_registrations"] : []),
        ...(indicator === "chargers" || indicator === "ratio" ? ["public_chargers"] : []),
      ].includes(dataset.id),
    );
    const data: ChartData = {
      id: `district-map-${indicator}`,
      title: indicatorLabels[indicator],
      subtitle: indicatorLabels[indicator],
      summary: "District observations; missing data is never zero.",
      type: "bar",
      unit:
        indicator === "usage"
          ? "kWh/charger/month"
          : indicator === "ratio"
            ? "chargers/1000 registrations"
            : indicator === "registrations"
              ? "vehicles"
              : "listed chargers",
      updated: sources
        .map((source) => source.metadata.retrieved_on)
        .sort()
        .at(-1)!,
      sources: sources.map((source) => ({
        name: source.metadata.source_name,
        url: source.metadata.source_url,
        licence: source.metadata.licence,
      })),
      versions: { ...catalogue.versions, renderer_version: "analytics_map_v1" },
      notes: [],
      rows: (all ? districts : filtered).map((district) => {
        const value = get(district.lgd_code);
        return {
          region: `${district.state_name} / ${district.district_name}`,
          period: "latest validated reporting period",
          indicator: indicatorLabels[indicator],
          series: "Districts",
          label: `${district.district_name} (LGD ${district.lgd_code})`,
          value: value.value,
          p10: value.p10,
          p90: value.p90,
          sample_size: value.value == null ? null : value.sample_size,
          status: value.value == null ? "missing" : value.p10 != null ? "estimate" : "observed",
        };
      }),
    };
    const href = URL.createObjectURL(
        new Blob(
          [chartCsv(data, data.rows, window.location.href, new Date().toISOString().slice(0, 10))],
          { type: "text/csv;charset=utf-8" },
        ),
      ),
      anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `${data.id}-${all ? "all" : "selection"}.csv`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  };
  return (
    <section className="analytics-section analytics-map" aria-labelledby={`${uid}-title`}>
      <h2 id={`${uid}-title`}>Explore district data</h2>
      <p>
        Listed chargers describe the verified source inventory, not exhaustive charging coverage.
        Registration totals require twelve complete months across all vehicle classes. Missing
        observations are not zero.
      </p>
      <label htmlFor={`${uid}-indicator`}>Map indicator</label>
      <select
        id={`${uid}-indicator`}
        value={indicator}
        onChange={(event) => setIndicator(event.target.value as Indicator)}
      >
        {Object.entries(indicatorLabels).map(([key, label]) => (
          <option key={key} value={key}>
            {label}
          </option>
        ))}
      </select>
      {paths.length ? (
        <svg
          className="analytics-district-map"
          viewBox="0 0 640 480"
          role="img"
          aria-label={`${indicatorLabels[indicator]}. Hatched districts have no published value. Use the district list or table to explore.`}
        >
          <defs>
            <pattern
              id={`${uid}-missing`}
              width="8"
              height="8"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="8" height="8" className="analytics-map-paper" />
              <line x1="0" x2="0" y1="0" y2="8" className="analytics-map-hatch" />
            </pattern>
          </defs>
          {paths.map(({ code, path }) => {
            const value = get(code),
              district = districts.find((district) => district.lgd_code === code);
            const wide =
              value.value != null &&
              value.p10 != null &&
              value.p90 != null &&
              (value.p90 - value.p10) / Math.max(Math.abs(value.value), 1) > 1;
            const step =
              value.value == null ? -1 : Math.min(4, Math.floor((value.value / (max || 1)) * 5));
            return (
              <path
                key={code}
                d={path}
                fillRule="evenodd"
                fill={step < 0 ? `url(#${uid}-missing)` : undefined}
                className={`analytics-map-district ${step >= 0 ? `analytics-map-step-${step}` : ""} ${wide ? "analytics-map-wide" : ""} ${selected === code ? "analytics-map-selected" : ""}`}
                onClick={() => setSelected(code)}
                onMouseEnter={() => setSelected(code)}
              >
                <title>
                  {district?.district_name ?? code}: {mapValueLabel(value)}
                  {wide ? "; Wide range" : ""}
                </title>
              </path>
            );
          })}
        </svg>
      ) : (
        <p className="analytics-preparation">
          Verified district boundaries are not available yet. The reference names below do not imply
          current geographic coverage.
        </p>
      )}
      <ul className="analytics-map-legend">
        <li>
          <span className="analytics-map-swatch analytics-map-missing" /> Not enough data yet
        </li>
        <li>
          <span className="analytics-map-swatch analytics-map-wide" /> Wide range (P90 − P10 exceeds
          P50)
        </li>
        {numbers.length > 0 &&
          breaks.slice(0, 5).map((start, index) => (
            <li key={index}>
              <span className={`analytics-map-swatch analytics-map-step-${index}`} />{" "}
              <span className="analytics-number">
                {numberLabel(start)}–{numberLabel(breaks[index + 1]!)}
              </span>
            </li>
          ))}
      </ul>
      <p>
        Sources and last updated:{" "}
        {catalogue.datasets
          .filter((dataset) =>
            [
              "district_reference",
              "district_boundaries",
              ...(indicator === "registrations" || indicator === "ratio"
                ? ["ev_registrations"]
                : []),
              ...(indicator === "chargers" || indicator === "ratio" ? ["public_chargers"] : []),
            ].includes(dataset.id),
          )
          .map((dataset) => (
            <span key={dataset.id}>
              <a href={dataset.metadata.source_url}>{dataset.metadata.source_name}</a> (
              {dataset.metadata.licence}), <time>{dataset.metadata.retrieved_on}</time>;{" "}
            </span>
          ))}{" "}
        {indicator === "usage" && "Usage publication is awaiting privacy and validation checks."}
      </p>
      <p role="status">
        {current
          ? `${current.district_name}, ${current.state_name}: ${mapValueLabel(get(current.lgd_code))}${get(current.lgd_code).note ? `. ${get(current.lgd_code).note}` : ""}`
          : "Select a district to see its value and range."}
      </p>
      <label htmlFor={`${uid}-search`}>Find a district on this map</label>
      <input
        id={`${uid}-search`}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <ul className="analytics-map-list">
        {filtered.slice(0, 20).map((district) => (
          <li key={district.lgd_code}>
            <button
              aria-pressed={selected === district.lgd_code}
              onClick={() => setSelected(district.lgd_code)}
            >
              {district.district_name} · {district.state_name}
            </button>
            {selected === district.lgd_code && (
              <Link to={`/data/district/${district.slug}`}>Open district page</Link>
            )}
          </li>
        ))}
      </ul>
      {filtered.length > 20 && (
        <p>
          Showing the first 20 list matches. Refine the search; the table contains all matching
          districts.
        </p>
      )}
      <div
        className="analytics-table-scroll"
        role="region"
        aria-label="District values table"
        tabIndex={0}
      >
        <table className="analytics-chart-table">
          <caption>{indicatorLabels[indicator]}</caption>
          <thead>
            <tr>
              <th
                scope="col"
                aria-sort={sort === "district" ? (descending ? "descending" : "ascending") : "none"}
              >
                <button
                  onClick={() => {
                    setSort("district");
                    setDescending(sort === "district" && !descending);
                  }}
                >
                  District
                </button>
              </th>
              <th scope="col">State</th>
              <th
                scope="col"
                aria-sort={sort === "value" ? (descending ? "descending" : "ascending") : "none"}
              >
                <button
                  onClick={() => {
                    setSort("value");
                    setDescending(sort === "value" && !descending);
                  }}
                >
                  Value and range
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((district) => (
              <tr key={district.lgd_code}>
                <th scope="row">
                  <Link to={`/data/district/${district.slug}`}>{district.district_name}</Link>
                </th>
                <td>{district.state_name}</td>
                <td className="analytics-number analytics-numeric">
                  {mapValueLabel(get(district.lgd_code))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="analytics-chart-controls">
        <button
          disabled={!filtered.length || indicator === "usage"}
          onClick={() => download(false)}
        >
          Download CSV (current selection)
        </button>
        <button
          disabled={!districts.length || indicator === "usage"}
          onClick={() => download(true)}
        >
          Download CSV (all data)
        </button>
      </div>
      <details>
        <summary>Output versions</summary>
        <dl>
          {Object.entries({ ...catalogue.versions, renderer_version: "analytics_map_v1" }).map(
            ([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{value}</dd>
              </div>
            ),
          )}
        </dl>
      </details>
    </section>
  );
}
