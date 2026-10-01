import { DistrictGrid } from "../expansion/Expansion";
import expansion from "virtual:analytics-expansion";
import { policyMarkers, policyNote } from "../expansion/model";
import { Link } from "react-router-dom";
import atlas from "virtual:analytics-atlas";
import catalogue from "virtual:analytics-public-data";
import { Chart } from "../chart/Chart";
import { numberLabel, type ChartData, type ChartRow } from "../chart/model";
import { publicDataVersions, type DatasetId, type District } from "../data/schemas";
import { formatRupeesPrecise } from "../../../lib/money";
import { DistrictMap } from "./DistrictMap";
import {
  districtValue,
  hasDistrictIndicator,
  latestMonth,
  monthOffset,
  neighbourCodes,
  registrationTotal,
} from "./model";

function chart(
  data: Omit<ChartData, "sources" | "updated" | "versions">,
  id: DatasetId,
): ChartData | null {
  const source = catalogue.datasets.find((dataset) => dataset.id === id);
  return source
    ? {
        ...data,
        sources: [
          {
            name: source.metadata.source_name,
            url: source.metadata.source_url,
            licence: source.metadata.licence,
          },
        ],
        updated: source.metadata.retrieved_on,
        versions: { ...publicDataVersions, renderer_version: "analytics_svg_v1" },
      }
    : null;
}
export function DistrictDetails({ district }: { district: District }) {
  const code = district.lgd_code,
    end = latestMonth(atlas),
    registrations = registrationTotal(atlas, code, end),
    previous = end ? registrationTotal(atlas, code, monthOffset(end, -12)) : null;
  const chargers = atlas.chargers.filter((row) => row.lgd_code === code),
    tariff = atlas.tariffs.filter((row) => row.state === district.state_name);
  const reference = catalogue.datasets.find((dataset) => dataset.id === "district_reference");
  const regRows = atlas.registrations.filter((row) => row.lgd_code === code);
  const classes = [...new Set(regRows.map((row) => row.vehicle_class))];
  const months = [...new Set(regRows.map((row) => row.month))].sort();
  const registrationChart = chart(
    {
      id: `registrations-${code}`,
      annotations: policyMarkers(expansion.policies, district.state_name, expansion.asOf),
      title: "How have EV registrations changed?",
      subtitle: "Recorded registrations by month and vehicle class, in vehicles.",
      summary: "Monthly registration observations; absent periods are labelled gaps.",
      type: "small-multiples",
      unit: "vehicles",
      notes: [
        policyNote,
        "A twelve-month total is available only when every vehicle class has explicit observations for all twelve months. These are new registrations, not the district's complete EV fleet.",
      ],
      rows: months.length
        ? Array.from(
            {
              length: Math.min(
                36,
                (Number(months.at(-1)!.slice(0, 4)) - Number(months[0]!.slice(0, 4))) * 12 +
                  Number(months.at(-1)!.slice(5)) -
                  Number(months[0]!.slice(5)) +
                  1,
              ),
            },
            (_, index) => monthOffset(months.at(-1)!, -index),
          )
            .reverse()
            .flatMap((month) =>
              classes.map((vehicleClass) => {
                const cells = regRows.filter(
                  (row) => row.month === month && row.vehicle_class === vehicleClass,
                );
                return {
                  region: `${district.state_name} / ${district.district_name}`,
                  period: month,
                  indicator: "Registrations",
                  series: vehicleClass,
                  label: month,
                  value: cells.length ? cells.reduce((sum, row) => sum + row.count, 0) : null,
                  status: cells.length ? "observed" : "missing",
                } as ChartRow;
              }),
            )
        : [],
    },
    "ev_registrations",
  );
  const opened = chargers.filter((row) => row.opened_month),
    openedMonths = [...new Set(opened.map((row) => row.opened_month!))].sort();
  const openingsChart = chart(
    {
      id: `chargers-${code}`,
      title: "When did the listed public chargers open?",
      subtitle: "Cumulative listed charger records with a known opening month, in chargers.",
      summary: "Partial source inventory with known opening dates.",
      type: "line",
      unit: "listed chargers",
      notes: [
        `${chargers.length - opened.length} listed records have no opening month and are excluded. This is not a complete historic network inventory.`,
      ],
      rows: openedMonths.map((month) => ({
        region: district.district_name,
        period: month,
        indicator: "Known openings",
        series: "Listed records",
        label: month,
        value: opened.filter((row) => row.opened_month! <= month).length,
        status: "observed" as const,
      })),
    },
    "public_chargers",
  );
  const neighbours = neighbourCodes(atlas.shapes, code),
    stateDistricts = catalogue.districts.filter((row) => row.state_name === district.state_name),
    stateValues = stateDistricts.map(
      (row) => districtValue(atlas, row.lgd_code, "registrations").value,
    ),
    stateAverage =
      stateValues.length && stateValues.every((value) => value != null)
        ? stateValues.reduce<number>((sum, value) => sum + value!, 0) / stateValues.length
        : null;
  const sourceLine = (id: DatasetId) => {
    const source = catalogue.datasets.find((dataset) => dataset.id === id);
    return source ? (
      <p>
        Source: <a href={source.metadata.source_url}>{source.metadata.source_name}</a>. Last
        updated: <time>{source.metadata.retrieved_on}</time>. {source.metadata.notes}
      </p>
    ) : (
      <p>Source verification is pending.</p>
    );
  };
  return (
    <>
      <p className="analytics-lead">{district.state_name}</p>
      <p>
        District name and LGD code <span className="analytics-number">{code}</span> come from our
        archived reference, retrieved <time>{reference?.metadata.retrieved_on}</time>. This is not a
        claim of current district coverage.{" "}
        <Link to="/data/sources">See the source and vintage.</Link>
      </p>
      {!hasDistrictIndicator(atlas, district) && (
        <div className="analytics-preparation">
          <p className="analytics-label">Being prepared</p>
          <p>
            No district indicators have been published here yet. Missing data will always be
            labelled, never shown as zero.
          </p>
        </div>
      )}
      <section className="analytics-section">
        <h2>Key figures</h2>
        <dl className="analytics-district-figures">
          <div>
            <dt>EV registrations, latest 12 months{end ? ` ending ${end}` : ""}</dt>
            <dd className="analytics-number">
              {registrations == null ? "Not enough data yet" : numberLabel(registrations)}
            </dd>
            <dt>Change from the preceding 12 months</dt>
            <dd className="analytics-number">
              {registrations != null && previous != null && previous > 0
                ? `${numberLabel(((registrations - previous) / previous) * 100)}%`
                : "Not enough data yet"}
            </dd>
            {sourceLine("ev_registrations")}
          </div>
          <div>
            <dt>Listed public chargers</dt>
            <dd className="analytics-number">
              {chargers.length ? numberLabel(chargers.length) : "Not enough data yet"}
            </dd>
            {chargers.length > 0 && (
              <p>
                AC:{" "}
                <span className="analytics-number">
                  {chargers.filter((row) => row.ac_or_dc === "AC").length}
                </span>
                . DC:{" "}
                <span className="analytics-number">
                  {chargers.filter((row) => row.ac_or_dc === "DC").length}
                </span>
                . Counts describe source records, not connectors or exhaustive coverage.
              </p>
            )}
            {sourceLine("public_chargers")}
          </div>
          <div>
            <dt>Listed chargers per 1,000 EV registrations</dt>
            <dd className="analytics-number">
              {districtValue(atlas, code, "ratio").value == null
                ? "Not enough data yet"
                : numberLabel(districtValue(atlas, code, "ratio").value!)}
            </dd>
            <p>
              Uses the latest complete twelve-month registrations as its denominator, not an EV
              fleet estimate.
            </p>
          </div>
          <div>
            <dt>Estimated monthly kWh per charger</dt>
            <dd>Not enough data yet</dd>
            <p>Only privacy-safe, validated Part 5 aggregates can appear here.</p>
          </div>
        </dl>
      </section>
      <DistrictGrid district={district} />
      <h2>Locator</h2>
      {atlas.shapes.some((shape) => shape.lgd_code === code) ? (
        <DistrictMap
          atlas={{ ...atlas, shapes: atlas.shapes.filter((shape) => shape.lgd_code === code) }}
          districts={[district]}
        />
      ) : (
        <p>
          Verified boundary geometry is not available for this district. A locator will appear once
          its LGD join and source licence are checked.
        </p>
      )}
      {registrationChart && regRows.length > 0 && <Chart data={registrationChart} />}
      {openingsChart && opened.length > 0 && <Chart data={openingsChart} />}
      <section className="analytics-section">
        <h2>Electricity tariffs for {district.state_name}</h2>
        {tariff.length ? (
          <>
            <ul>
              {tariff.map((row, index) => (
                <li key={index}>
                  {row.discom}, {row.category}:{" "}
                  <span className="analytics-number">
                    {formatRupeesPrecise(row.energy_charge_paise_per_kwh)}
                  </span>{" "}
                  per kWh, effective <time>{row.effective_from}</time>. Fixed/demand charge:{" "}
                  {row.demand_or_fixed_charge_paise == null
                    ? "Unknown"
                    : `${formatRupeesPrecise(row.demand_or_fixed_charge_paise)} (${row.unit})`}
                  . {row.tod_rules} {row.notes}
                </li>
              ))}
            </ul>
            {sourceLine("ev_tariffs")}
          </>
        ) : (
          <p>Tariff orders are awaiting verification. Unknown charges are not zero.</p>
        )}
      </section>
      <section className="analytics-section">
        <h2>State and neighbouring districts</h2>
        <p>
          State mean of latest twelve-month registrations:{" "}
          <span className="analytics-number">
            {stateAverage == null ? "Not enough data yet" : numberLabel(stateAverage)}
          </span>
          . A mean is shown only when every district in the reference has complete observations.
        </p>
        {neighbours.length ? (
          <ul>
            {neighbours.map((neighbour) => {
              const row = catalogue.districts.find((district) => district.lgd_code === neighbour);
              return row ? (
                <li key={neighbour}>
                  <Link to={`/data/district/${row.slug}`}>{row.district_name}</Link>:{" "}
                  {districtValue(atlas, neighbour, "registrations").value == null
                    ? "Not enough data yet"
                    : numberLabel(districtValue(atlas, neighbour, "registrations").value!)}
                </li>
              ) : null;
            })}
          </ul>
        ) : (
          <p>
            Neighbour comparisons need verified boundaries with shared edges; none are available
            yet.
          </p>
        )}
      </section>
      <section className="analytics-section">
        <h2>What we don’t know yet</h2>
        <ul>
          {registrations == null && (
            <li>A complete twelve-month registration series across all vehicle classes.</li>
          )}
          {!chargers.length && <li>A verified public charger inventory for this district.</li>}
          {!tariff.length && <li>Verified state electricity tariff orders.</li>}
          {!atlas.shapes.some((shape) => shape.lgd_code === code) && (
            <li>A licensed boundary and neighbouring district joins.</li>
          )}
          <li>Privacy-safe validated monthly usage estimates.</li>
          <li>Source completeness and differences from current district boundaries.</li>
        </ul>
      </section>
      <section className="analytics-section">
        <h2>Relevant insights</h2>
        <p>
          No district insights have been published yet.{" "}
          <Link to="/data/insights">Browse insights as they become available.</Link>
        </p>
      </section>
    </>
  );
}
