import type { PublicCatalogue } from "../data/schemas";
import type { Expansion } from "./model";
import { latestPerformance, plannedAmenities, policyRows } from "./model";

export function expansionLinks(data: Expansion, catalogue: PublicCatalogue) {
  const has = (id: string) =>
    catalogue.datasets.some((source) => source.id === id && source.rows > 0);
  const electricity =
    (has("discom_performance") && latestPerformance(data.performance, data.asOf).length > 0) ||
    (has("supply_hours") && data.supply.some((row) => row.period_end <= data.asOf)) ||
    (has("state_ev_policies") && policyRows(data.policies, data.asOf).length > 0);
  const corridors =
    has("nhai_wayside_amenities") && plannedAmenities(data.amenities, data.asOf).length > 0;
  return [
    ...(electricity
      ? [{ to: "/data/electricity", label: "Electricity and policy context, with dated sources" }]
      : []),
    ...(corridors
      ? [{ to: "/data/corridors", label: "Planned highway amenities, with dated sources" }]
      : []),
  ];
}
