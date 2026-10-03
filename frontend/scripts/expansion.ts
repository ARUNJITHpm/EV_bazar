import { parseCsv } from "./csv.ts";
import { rowSchemas, type CsvDatasetId } from "../src/features/analytics/data/schemas.ts";
import type { Expansion } from "../src/features/analytics/expansion/model.ts";
import type { LoadedPublicData } from "./public-data.ts";

// Only the already validated public artifact tree is reachable here.
export function buildExpansion(loaded: LoadedPublicData, asOf: string): Expansion {
  function rows<T extends CsvDatasetId>(id: T) {
    const file = loaded.artifacts.find((f) => f.name === `analytics-data/${id}/data.csv`);
    if (!file) return [];
    const parsed = parseCsv(file.source, file.name),
      header = parsed.shift()!.values;
    return parsed.map((r) =>
      rowSchemas[id].parse(Object.fromEntries(header.map((name, i) => [name, r.values[i]]))),
    );
  }
  return {
    asOf,
    performance: rows("discom_performance") as Expansion["performance"],
    supply: rows("supply_hours") as Expansion["supply"],
    policies: rows("state_ev_policies") as Expansion["policies"],
    amenities: rows("nhai_wayside_amenities") as Expansion["amenities"],
    consumption: rows("cea_ev_consumption") as Expansion["consumption"],
  };
}
