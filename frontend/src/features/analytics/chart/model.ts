import { publicDataVersions } from "../data/schemas";

export type ChartType = "line" | "bar" | "horizontal-bar" | "range" | "small-multiples";
export interface ChartRow {
  region: string;
  period: string;
  indicator: string;
  series: string;
  label: string;
  value: number | null;
  p10?: number | null;
  p90?: number | null;
  status: "observed" | "estimate" | "missing" | "suppressed";
  sample_size?: number | null;
}
export interface ChartAnnotation {
  date: string;
  label: string;
  source_url: string;
}
export interface ChartReference {
  value: number;
  label: string;
}
export interface ChartData {
  annotations?: readonly ChartAnnotation[];
  reference?: ChartReference;
  id: string;
  title: string;
  subtitle: string;
  summary: string;
  type: ChartType;
  unit: string;
  rows: readonly ChartRow[];
  sources: readonly {
    name: string;
    url: string;
    licence: string;
    licence_url?: string;
    attribution?: string;
  }[];
  updated: string;
  notes: readonly string[];
  versions: Record<keyof typeof publicDataVersions, string>;
}
export interface ChartFilters {
  region: string;
  period: string;
  indicator: string;
}
export function chartFilters(search: string, id: string): ChartFilters {
  const params = new URLSearchParams(search);
  return {
    region: params.get(`${id}.region`) ?? "",
    period: params.get(`${id}.period`) ?? "",
    indicator: params.get(`${id}.indicator`) ?? "",
  };
}
export function selectRows(rows: readonly ChartRow[], filters: ChartFilters) {
  return rows.filter(
    (row) =>
      row.region
        .toLocaleLowerCase("en-IN")
        .includes(filters.region.trim().toLocaleLowerCase("en-IN")) &&
      (!filters.period || row.period === filters.period) &&
      (!filters.indicator || row.indicator === filters.indicator),
  );
}
export function validateChart(data: ChartData) {
  if (data.reference && (!Number.isFinite(data.reference.value) || !data.reference.label))
    throw new Error("Reference needs a finite value and label");
  for (const marker of data.annotations ?? []) {
    const parsed = new Date(`${marker.date}T00:00:00Z`);
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(marker.date) ||
      !Number.isFinite(parsed.getTime()) ||
      parsed.toISOString().slice(0, 10) !== marker.date ||
      !marker.label ||
      !/^https?:\/\//.test(marker.source_url)
    )
      throw new Error("Policy marker needs a valid date, label and notification URL");
  }
  if (!/^[a-z][a-z0-9-]*$/.test(data.id)) throw new Error("Chart id must be a stable slug");
  if (data.type !== "small-multiples" && new Set(data.rows.map((row) => row.series)).size > 3)
    throw new Error("Use small multiples for more than three series");
  const categories = new Set<string>();
  const date = new Date(`${data.updated}T00:00:00Z`);
  if (
    !/^\d{4}-\d{2}-\d{2}$/.test(data.updated) ||
    !Number.isFinite(date.getTime()) ||
    date.toISOString().slice(0, 10) !== data.updated
  )
    throw new Error("Chart needs a valid update date");
  if (
    !data.sources.length ||
    !data.sources.every((source) => /^https?:\/\//.test(source.url) && source.licence)
  )
    throw new Error("Chart needs sources and licences");
  if (
    !Object.values(data.versions).every(Boolean) ||
    Object.keys(publicDataVersions).some(
      (key) => !data.versions[key as keyof typeof publicDataVersions],
    )
  )
    throw new Error("Chart needs all version stamps");
  for (const row of data.rows) {
    const category = JSON.stringify([row.series, row.label]);
    if (categories.has(category))
      throw new Error(
        "Each series/category pair must be unique; distinguish regions and indicators in series labels",
      );
    categories.add(category);
    if (row.sample_size != null && (!Number.isSafeInteger(row.sample_size) || row.sample_size < 0))
      throw new Error("Sample sizes must be non-negative integers");
    if (
      [row.value, row.p10, row.p90, row.sample_size].some(
        (value) => value != null && !Number.isFinite(value),
      )
    )
      throw new Error("Chart values must be finite");
    if (row.status === "missing" || row.status === "suppressed") {
      if (row.value !== null || row.p10 != null || row.p90 != null || row.sample_size != null)
        throw new Error("Missing and suppressed rows must not disclose values or sample sizes");
    } else if (row.value === null) throw new Error("Available rows need a value");
    if (
      row.status === "estimate" &&
      (row.p10 == null ||
        row.p90 == null ||
        row.value == null ||
        row.p10 > row.value ||
        row.value > row.p90)
    )
      throw new Error("Estimates require ordered P10/P50/P90");
    if (row.status !== "estimate" && (row.p10 != null || row.p90 != null))
      throw new Error("Ranges must be labelled estimates");
  }
}
export function citation(data: ChartData, url: string, accessed: string) {
  return `Chargeworthy Data, ${data.title}, ${url}, accessed ${accessed}. Original chart: CC BY 4.0. Source data: ${data.sources.map((source) => `${source.name} (${source.licence})${source.attribution ? `; ${source.attribution}` : ""}`).join("; ")}.`;
}
const csvCell = (value: unknown) => {
  // Neutralise spreadsheet formulas in text cells, retaining raw numeric cells.
  const text =
    typeof value === "string" && /^[\s]*[=+\-@]/.test(value) ? `'${value}` : String(value ?? "");
  return `"${text.replaceAll('"', '""')}"`;
};
export function chartCsv(
  data: ChartData,
  rows: readonly ChartRow[],
  url: string,
  accessed: string,
) {
  const fields = [
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
  const versions = Object.keys(publicDataVersions) as (keyof typeof publicDataVersions)[];
  const header = [
    ...fields,
    "unit",
    "title",
    "source_urls",
    "source_licences",
    "last_updated",
    "citation",
    ...versions,
  ];
  return (
    "\uFEFF# Chargeworthy Data: " +
    JSON.stringify({
      original_content_licence: "CC BY 4.0",
      licence_url: "https://creativecommons.org/licenses/by/4.0/",
      source_data: data.sources,
      measure_notes: data.notes,
      policy_markers: data.annotations ?? [],
      reference: data.reference ?? null,
      citation: citation(data, url, accessed),
      notes: "Third-party data retains its own licence. Credit the source and identify changes.",
    }) +
    "\r\n" +
    [
      header,
      ...rows.map((row) => [
        ...fields.map((key) => row[key]),
        data.unit,
        data.title,
        data.sources.map((source) => source.url).join("; "),
        data.sources.map((source) => `${source.name}: ${source.licence}`).join("; "),
        data.updated,
        citation(data, url, accessed),
        ...versions.map((key) => data.versions[key]),
      ]),
    ]
      .map((row) => row.map(csvCell).join(","))
      .join("\r\n") +
    "\r\n"
  );
}
export function linearScale(min: number, max: number, start: number, end: number) {
  return (value: number) => start + ((value - min) / (max - min || 1)) * (end - start);
}
export function valueDomain(rows: readonly ChartRow[]): [number, number] {
  const values = rows.flatMap((row) =>
    [row.value, row.p10, row.p90].filter((value): value is number => value != null),
  );
  const min = values.reduce((bound, value) => Math.min(bound, value), 0),
    max = values.reduce((bound, value) => Math.max(bound, value), 0);
  return min === max ? [0, 1] : [min, max];
}
export const numberLabel = (value: number) =>
  value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
export const rowValue = (row: ChartRow) =>
  row.value == null
    ? "Not enough data yet"
    : row.status === "estimate"
      ? `Estimate: ${numberLabel(row.value)} (P10 ${numberLabel(row.p10!)} – P90 ${numberLabel(row.p90!)})`
      : numberLabel(row.value);
