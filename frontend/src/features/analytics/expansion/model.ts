import type { z } from "zod";
import type { rowSchemas, PublicCatalogue, DatasetId } from "../data/schemas";
import { publicDataVersions } from "../data/schemas";
import type { ChartData, ChartRow } from "../chart/model";

export type Performance = z.infer<typeof rowSchemas.discom_performance>;
export type Supply = z.infer<typeof rowSchemas.supply_hours>;
export type Policy = z.infer<typeof rowSchemas.state_ev_policies>;
export type Amenity = z.infer<typeof rowSchemas.nhai_wayside_amenities>;
export interface Expansion {
  asOf: string;
  performance: Performance[];
  supply: Supply[];
  policies: Policy[];
  amenities: Amenity[];
}
export const outageNote =
  "AT&C loss is electricity that is not billed or not paid for, plus technical loss. It is not a measure of outages or voltage at any site.";
export const policyNote =
  "Dates are context; the chart does not show that a policy caused a change.";

export function policyStatus(row: Policy, asOf: string, rows: Policy[] = []) {
  const next = rows.find(
    (r) =>
      r.state === row.state &&
      r.supersedes_ref === row.notification_ref &&
      r.notified_on <= asOf &&
      r.valid_from <= asOf,
  );
  if (next) return `Superseded from ${next.valid_from}`;
  if (row.notified_on > asOf) return "Not yet notified";
  if (row.valid_from > asOf) return "Not yet in force";
  // The register uses an inclusive last valid day.
  if (row.valid_to && row.valid_to < asOf) return `Expired ${row.valid_to}`;
  return row.valid_to ? `In force through ${row.valid_to}` : "End date not published";
}
export function policyRows(rows: Policy[], asOf: string, state?: string) {
  return rows.filter(
    (row) => (!state || row.state === state || row.state === "central") && row.notified_on <= asOf,
  );
}
export function policyMarkers(rows: Policy[], state: string, asOf: string) {
  const markers = policyRows(rows, asOf, state).flatMap((row) => [
    { date: row.valid_from, label: `${row.policy_name}: start`, source_url: row.source_url },
    ...(row.valid_to
      ? [
          {
            date: row.valid_to,
            label: `${row.policy_name}: last valid day`,
            source_url: row.source_url,
          },
        ]
      : []),
  ]);
  return markers.filter(
    (m, i) =>
      markers.findIndex(
        (a) => a.date === m.date && a.label === m.label && a.source_url === m.source_url,
      ) === i,
  );
}
// Never choose an arbitrary edition where a year contains competing snapshots.
// State summaries and an explicit national row are separate from named utilities.
export function latestPerformance(rows: Performance[], asOf: string) {
  const eligible = rows.filter((r) => `${Number(r.fiscal_year.slice(0, 4)) + 1}-03-31` <= asOf);
  const year = eligible
    .map((r) => r.fiscal_year)
    .sort()
    .at(-1);
  const latest = eligible.filter((r) => r.fiscal_year === year);
  return new Set(latest.map((r) => r.source_edition)).size === 1 &&
    new Set(latest.map((r) => r.discom_id)).size === latest.length
    ? latest
    : [];
}
export function latestSupply(rows: Supply[], asOf: string, state?: string, district?: number) {
  const eligible = rows.filter(
    (r) =>
      r.period_end <= asOf &&
      (!state || r.state === state) &&
      (district == null || r.lgd_code == null || r.lgd_code === district),
  );
  // Retain separate geography, definition and rural/urban series; never average them.
  const key = (r: Supply) =>
    JSON.stringify([
      r.state,
      r.lgd_code,
      r.discom_id,
      r.area_type,
      r.supply_definition,
      r.period_type,
    ]);
  return eligible.filter((r) => {
    const group = eligible.filter((v) => key(v) === key(r));
    const end = group
      .map((v) => v.period_end)
      .sort()
      .at(-1);
    return r.period_end === end && group.filter((v) => v.period_end === end).length === 1;
  });
}
export function sourceChart(
  catalogue: PublicCatalogue,
  id: DatasetId,
  data: Omit<ChartData, "sources" | "updated" | "versions">,
): ChartData | null {
  const source = catalogue.datasets.find((d) => d.id === id);
  if (!source) return null;
  return {
    ...data,
    sources: [
      {
        name: source.metadata.source_name,
        url: source.metadata.source_url,
        licence: source.metadata.licence,
        attribution: source.metadata.attribution,
      },
    ],
    updated: source.metadata.retrieved_on,
    versions: { ...publicDataVersions, renderer_version: "analytics_svg_v1" },
  };
}
export function performanceCharts(data: Expansion, catalogue: PublicCatalogue): ChartData[] {
  const latest = latestPerformance(data.performance, data.asOf);
  const national = latest.filter((r) => r.state === "India" && r.discom_id === "national");
  const utilities = latest.filter(
    (r) => r.state !== "India" && !["national", "state_total"].includes(r.discom_id),
  );
  const charts: ChartData[] = [];
  for (const state of [...new Set(utilities.map((r) => r.state))].sort()) {
    const rows = utilities.filter((r) => r.state === state);
    const reference =
      national.length === 1 && rows.every((r) => r.metric_basis === national[0]!.metric_basis)
        ? national[0]
        : null;
    const chart = sourceChart(catalogue, "discom_performance", {
      id: `atc-${state.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
      title: `AT&C loss: ${state}`,
      subtitle: `Published utility observations, ${rows[0]!.fiscal_year}; ${rows[0]!.source_edition}.`,
      summary: `AT&C loss by utility in ${state}. ${outageNote}`,
      type: "horizontal-bar",
      unit: "%",
      reference: reference
        ? {
            value: reference.atc_loss_pct,
            label: `India, ${reference.fiscal_year}, ${reference.source_edition}`,
          }
        : undefined,
      rows: rows.map((r): ChartRow => ({
        region: r.state,
        period: r.fiscal_year,
        indicator: "AT&C loss",
        series: "Utilities",
        label: r.discom,
        value: r.atc_loss_pct,
        status: "observed",
      })),
      notes: [
        outageNote,
        reference
          ? "The national reference uses the same edition, year and metric basis."
          : "A comparable national reference is not available; no utility average is substituted.",
      ],
    });
    if (chart) charts.push(chart);
    const ids = new Set(rows.map((r) => r.discom_id));
    const years = [
      ...new Set(
        data.performance
          .filter(
            (r) =>
              r.state === state &&
              ids.has(r.discom_id) &&
              `${Number(r.fiscal_year.slice(0, 4)) + 1}-03-31` <= data.asOf,
          )
          .map((r) => r.fiscal_year),
      ),
    ].sort();
    const trend = sourceChart(catalogue, "discom_performance", {
      id: `atc-trend-${state.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
      title: `AT&C loss over time: ${state}`,
      subtitle: "Each panel is one utility; conflicting editions are withheld.",
      summary: outageNote,
      type: "small-multiples",
      unit: "%",
      rows: rows.flatMap((utility) =>
        years.map((year): ChartRow => {
          const cells = data.performance.filter(
            (r) => r.state === state && r.discom_id === utility.discom_id && r.fiscal_year === year,
          );
          const value =
            cells.length === 1 && cells[0]!.metric_basis === utility.metric_basis
              ? cells[0]!.atc_loss_pct
              : null;
          return {
            region: state,
            period: year,
            indicator: "AT&C loss",
            series: utility.discom,
            label: year,
            value,
            status: value == null ? "missing" : "observed",
          };
        }),
      ),
      notes: [
        outageNote,
        "Different editions and changes in metric basis are not silently joined.",
      ],
    });
    if (trend && years.length > 1) charts.push(trend);
  }
  return charts;
}
export function plannedAmenities(rows: Amenity[], asOf: string) {
  const dated = rows.filter(
    (r) =>
      r.status_as_of != null &&
      r.status_as_of <= asOf &&
      r.source_doc_date != null &&
      r.source_doc_date <= asOf,
  );
  const latest = dated.filter((r) => {
    const group = dated.filter((v) => v.wsa_id === r.wsa_id);
    const end = group
      .map((v) => `${v.status_as_of}/${v.source_doc_date}`)
      .sort()
      .at(-1);
    return (
      `${r.status_as_of}/${r.source_doc_date}` === end &&
      group.filter((v) => `${v.status_as_of}/${v.source_doc_date}` === end).length === 1
    );
  });
  return latest.filter(
    (r) =>
      r.ev_charging_listed === "true" &&
      r.status_as_of != null &&
      r.status_as_of <= asOf &&
      r.source_doc_date != null &&
      r.source_doc_date <= asOf &&
      /^(planned|awarded)$/i.test(r.status.trim()),
  );
}
