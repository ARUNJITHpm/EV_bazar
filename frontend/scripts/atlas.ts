import { parseCsv } from "./csv.ts";
import { rowSchemas, type CsvDatasetId } from "../src/features/analytics/data/schemas.ts";
import {
  decodeTopology,
  type Atlas,
  type Topology,
} from "../src/features/analytics/districts/model.ts";
import type { LoadedPublicData } from "./public-data.ts";
export function buildAtlas(loaded: LoadedPublicData, includeGeometry = true): Atlas {
  function rows<T extends CsvDatasetId>(id: T) {
    const artifact = loaded.artifacts.find((file) => file.name === `analytics-data/${id}/data.csv`);
    if (!artifact) return [];
    const parsed = parseCsv(artifact.source, artifact.name),
      header = parsed.shift()!.values;
    return parsed.map((row) =>
      rowSchemas[id].parse(
        Object.fromEntries(header.map((name, index) => [name, row.values[index]])),
      ),
    );
  }
  const geometry = loaded.artifacts.find(
    (file) => file.name === "analytics-data/district_boundaries/data.topojson",
  );
  return {
    registrations: rows("ev_registrations") as Atlas["registrations"],
    chargers: rows("public_chargers") as Atlas["chargers"],
    tariffs: rows("ev_tariffs") as Atlas["tariffs"],
    shapes:
      includeGeometry && geometry ? decodeTopology(JSON.parse(geometry.source) as Topology) : [],
  };
}
