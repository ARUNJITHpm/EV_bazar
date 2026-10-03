import expansion from "virtual:analytics-expansion";
import catalogue from "virtual:analytics-public-data";
import { ProgressiveChart as Chart } from "../chart/ProgressiveChart";
import { numberLabel } from "../chart/model";
import type { DatasetId, District } from "../data/schemas";
import { stateLabel } from "../districts/model";
import {
  consumptionCharts,
  consumptionNote,
  latestSupply,
  outageNote,
  performanceCharts,
  plannedAmenities,
  policyNote,
  policyRows,
  policyStatus,
  sourceChart,
  type Policy,
} from "./model";

/** Several sources for one figure: pending ones share a single line rather than repeat it. */
export function SourceLines({ ids }: { ids: DatasetId[] }) {
  const published = ids.filter((id) => catalogue.datasets.some((d) => d.id === id));
  const pending = ids.find((id) => !published.includes(id));
  return (
    <>
      {published.map((id) => (
        <SourceLine key={id} id={id} />
      ))}
      {pending && <SourceLine id={pending} />}
    </>
  );
}

export function SourceLine({ id }: { id: DatasetId }) {
  const source = catalogue.datasets.find((d) => d.id === id);
  return source ? (
    <p>
      Source: <a href={source.metadata.source_url}>{source.metadata.source_name}</a>. Retrieved{" "}
      <time dateTime={source.metadata.retrieved_on}>{source.metadata.retrieved_on}</time>. Coverage:{" "}
      {source.metadata.geography_level}. Reporting period: {source.metadata.time_coverage}.{" "}
      {source.metadata.notes}
    </p>
  ) : (
    <p>
      Source review is pending. <a href={`/data/sources#source-${id}`}>Check source availability</a>
      .
    </p>
  );
}

export function Policies({ state }: { state?: string }) {
  const rows = policyRows(expansion.policies, expansion.asOf, state);
  // One policy can have many incentive clauses. Retain validity distinctions.
  const key = (r: Policy) =>
    JSON.stringify([r.state, r.notification_ref, r.policy_name, r.valid_from, r.valid_to]);
  const unique = rows.filter((r, i) => rows.findIndex((a) => key(a) === key(r)) === i);
  return (
    <section
      className="analytics-section analytics-context"
      id={state ? undefined : "policies-in-force"}
    >
      <h2>Policies in force{state ? `: ${stateLabel(state)}` : ""}</h2>
      <p>
        Status at the data-page build date, <time>{expansion.asOf}</time>. Notifications and
        amendments require human review. An unpublished end date does not establish that a policy is
        still in force.
      </p>
      {unique.length ? (
        <div
          className="analytics-table-scroll"
          role="region"
          aria-label="Policy register"
          tabIndex={0}
        >
          <table className="analytics-chart-table analytics-policy-table">
            <caption>Reviewed policy register, including expired policies</caption>
            <thead>
              <tr>
                <th scope="col">State and policy</th>
                <th scope="col">Validity</th>
                <th scope="col">Status</th>
                <th scope="col">Notification</th>
              </tr>
            </thead>
            <tbody>
              {unique.map((r) => (
                <tr key={key(r)}>
                  <th scope="row">
                    {r.state}: {r.policy_name}
                  </th>
                  <td>
                    <time>{r.valid_from}</time> to{" "}
                    {r.valid_to ? <time>{r.valid_to}</time> : "End date not published"}
                  </td>
                  <td>{policyStatus(r, expansion.asOf, rows)}</td>
                  <td>
                    <a href={r.source_url}>{r.notification_ref}</a>, notified{" "}
                    <time>{r.notified_on}</time>. Recorded <time>{r.recorded_on}</time>.
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p>Not available yet. Notified policies and their amendments are awaiting verification.</p>
      )}
      <p>
        {policyNote} Policy descriptions do not change the financial assumptions in a site report.
      </p>
      <SourceLine id="state_ev_policies" />
    </section>
  );
}

export function ElectricityContext() {
  const charts = performanceCharts(expansion, catalogue);
  const consumption = consumptionCharts(expansion, catalogue);
  const supply = latestSupply(expansion.supply, expansion.asOf);
  const supplyChart = sourceChart(catalogue, "supply_hours", {
    id: "area-supply-hours",
    title: "Average hours of electricity supply",
    subtitle:
      "Published area averages, in hours per day. Separate coverage and definitions are retained.",
    summary: "Area averages cannot establish an individual feeder's reliability.",
    type: "horizontal-bar",
    unit: "hours/day",
    rows: supply.map((r) => ({
      region: r.state,
      period: r.published_period_label,
      indicator: r.supply_definition,
      series: "Area observations",
      label: `${r.area_type} / ${r.state} / ${r.discom ?? "statewide"} / ${r.lgd_code ?? "no district join"} / ${r.published_period_label} / ${r.supply_definition} / ${r.period_type}`,
      value: r.avg_supply_hours_per_day,
      status: "observed" as const,
    })),
    notes: [
      "An area average is not an outage measurement at a station. Rural and urban values are not averaged together.",
      ...supply.map(
        (r) =>
          `${r.state}, ${r.area_type}, ${r.published_period_label}: ${r.period_start} to ${r.period_end}; ${r.supply_definition}. ${r.source_name}, ${r.source_url}; retrieved ${r.retrieved_on}. ${r.notes}`,
      ),
    ],
  });
  return (
    <>
      <section className="analytics-section analytics-context" id="ev-charging-electricity">
        <h2>Electricity used by EV charging</h2>
        <p>{consumptionNote}</p>
        {consumption.length ? (
          consumption.map((data) => <Chart key={data.id} data={data} />)
        ) : (
          <p>Not available yet. CEA's monthly reports have not been loaded.</p>
        )}
        <SourceLine id="cea_ev_consumption" />
      </section>
      <section className="analytics-section analytics-context">
        <h2>Electricity billing and collection losses</h2>
        <p>{outageNote}</p>
        {charts.length ? (
          charts.map((data) => <Chart key={data.id} data={data} />)
        ) : (
          <p>
            Not available yet. A reviewed PFC edition and comparable national reference are awaiting
            source approval. Conflicting editions are withheld.
          </p>
        )}
        <SourceLine id="discom_performance" />
      </section>
      <section className="analytics-section analytics-context">
        <h2>Supply hours</h2>
        {supplyChart && supply.length ? (
          <Chart data={supplyChart} />
        ) : (
          <p>
            Not available yet. Published supply definitions, reporting periods and reuse terms need
            verification.
          </p>
        )}
        <SourceLine id="supply_hours" />
      </section>
      <Policies />
    </>
  );
}

export function DistrictGrid({ district }: { district: District }) {
  // No reviewed serving-utility crosswalk exists. State performance must not
  // become a claim that a particular DISCOM serves this pin/district.
  const supply = latestSupply(
    expansion.supply.filter((r) => r.discom_id == null),
    expansion.asOf,
    district.state_name,
    district.lgd_code,
  );
  return (
    <section className="analytics-section analytics-context">
      <h2>Grid and policy</h2>
      <h3>Serving electricity utilities</h3>
      <p>
        Not available yet. A verified district-to-utility mapping is needed before assigning a
        serving DISCOM or its AT&C loss.
      </p>
      <p>{outageNote}</p>
      <SourceLine id="discom_performance" />
      <h3>Area supply hours</h3>
      {supply.length ? (
        <ul>
          {supply.map((r, i) => (
            <li key={i}>
              <span className="analytics-number">{numberLabel(r.avg_supply_hours_per_day)}</span>{" "}
              hours/day, {r.area_type};{" "}
              {r.lgd_code === district.lgd_code
                ? "district coverage"
                : `${r.state} statewide context, not district supply`}
              . {r.published_period_label}, <time>{r.period_start}</time> to{" "}
              <time>{r.period_end}</time>. Definition: {r.supply_definition}. Source:{" "}
              <a href={r.source_url}>{r.source_name}</a>, retrieved <time>{r.retrieved_on}</time>.{" "}
              {r.notes}
            </li>
          ))}
        </ul>
      ) : (
        <p>Not available yet. Area averages cannot establish this site's outage hours.</p>
      )}
      <SourceLine id="supply_hours" />
      <Policies state={district.state_name} />
      <h3>EVs per public charger</h3>
      <p>
        Not available yet for this district or its state. New registrations over twelve months are
        not the total EV fleet; no fleet-to-charger ratio is inferred from them.
      </p>
      <SourceLines ids={["ev_registrations", "public_chargers"]} />
    </section>
  );
}

export function CorridorsContext() {
  const amenities = plannedAmenities(expansion.amenities, expansion.asOf);
  return (
    <>
      <section className="analytics-section analytics-context">
        <h2>Verified fast-charger gaps</h2>
        <p>
          Not available yet. Gaps need verified operating DC fast chargers joined to the same
          connected national-highway geometry, with a reviewed snap tolerance. Straight-line
          distances between listings cannot establish a highway gap.
        </p>
        <p>
          Planned and awarded amenities never shorten a verified gap. No corridor coverage or gap
          length is claimed here.
        </p>
      </section>
      <section className="analytics-section analytics-context">
        <h2>Planned wayside amenities</h2>
        {amenities.length ? (
          <ul>
            {amenities.map((r) => (
              <li key={r.wsa_id}>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 14 14"
                  role="img"
                  aria-label="Planned, not a verified charger"
                >
                  <circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" />
                </svg>{" "}
                {r.nh_ref}, {r.state},{" "}
                {r.chainage_km == null
                  ? "chainage not published"
                  : `${numberLabel(r.chainage_km)} km published chainage`}
                : {r.status}, not a verified charger. Status dated <time>{r.status_as_of}</time>;
                document <time>{r.source_doc_date}</time>, page {r.source_page}. {r.notes}
              </li>
            ))}
          </ul>
        ) : (
          <p>
            Not available yet. Dated planned or awarded sites must explicitly list EV charging.
            Historical entries and unknown charging flags do not establish a planned charger.
          </p>
        )}
        <SourceLine id="nhai_wayside_amenities" />
      </section>
    </>
  );
}
