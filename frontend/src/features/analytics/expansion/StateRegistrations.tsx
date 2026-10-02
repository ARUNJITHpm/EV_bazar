import atlas from "virtual:analytics-atlas";
import catalogue from "virtual:analytics-public-data";
import expansion from "virtual:analytics-expansion";
import { monthOffset } from "../districts/model";
import { ProgressiveChart as Chart } from "../chart/ProgressiveChart";
import type { ChartRow } from "../chart/model";
import { SourceLine } from "./Expansion";
import { policyMarkers, policyNote, sourceChart } from "./model";

export function StateRegistrations() {
  const states = [...new Set(atlas.registrations.map((r) => r.state))].sort();
  return (
    <section className="analytics-section analytics-context">
      <h2>State registrations and policy dates</h2>
      <p>
        {policyNote} Policy markers use reviewed notification dates and validity; missing policy
        evidence produces no markers.
      </p>
      {states.length ? (
        states.map((state) => {
          const records = atlas.registrations.filter((r) => r.state === state);
          const observedMonths = [...new Set(records.map((r) => r.month))].sort();
          const first = observedMonths[0]!,
            last = observedMonths.at(-1)!;
          const span =
            (Number(last.slice(0, 4)) - Number(first.slice(0, 4))) * 12 +
            Number(last.slice(5)) -
            Number(first.slice(5)) +
            1;
          const months = Array.from({ length: Math.min(span, 36) }, (_, i) =>
            monthOffset(last, -i),
          ).reverse();
          const classes = [...new Set(records.map((r) => r.vehicle_class))].sort();
          const districts = catalogue.districts.filter((d) => d.state_name === state);
          const data = sourceChart(catalogue, "ev_registrations", {
            id: `state-registrations-${state.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`,
            title: `New EV registrations: ${state}`,
            subtitle: "Monthly registrations by vehicle class; not the total EV fleet.",
            summary: `Recorded registrations in ${state}. ${policyNote}`,
            type: "small-multiples",
            unit: "vehicles",
            annotations: policyMarkers(expansion.policies, state, expansion.asOf),
            rows: classes.flatMap((vehicleClass) =>
              months.map((month): ChartRow => {
                const cells = records.filter(
                  (r) => r.month === month && r.vehicle_class === vehicleClass,
                );
                const complete =
                  districts.length > 0 &&
                  districts.every((d) => cells.some((r) => r.lgd_code === d.lgd_code));
                return {
                  region: state,
                  period: month,
                  indicator: "New registrations",
                  series: vehicleClass,
                  label: month,
                  value: complete ? cells.reduce((sum, r) => sum + r.count, 0) : null,
                  status: complete ? "observed" : "missing",
                };
              }),
            ),
            notes: [
              policyNote,
              "A state observation is withheld when any reference district lacks observations for that class and month. Published RTO allocations retain their source limits.",
            ],
          });
          return data ? <Chart key={state} data={data} /> : null;
        })
      ) : (
        <p>
          Not available yet. Reviewed monthly registration series are needed before policy markers
          can be plotted.
        </p>
      )}
      <SourceLine id="state_ev_policies" />
    </section>
  );
}
