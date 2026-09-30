import { mkdir, writeFile, access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import {
  datasetFiles,
  datasetIds,
  rowSchemas,
  type CsvDatasetId,
} from "../src/features/analytics/data/schemas.ts";

// Explicit templates contain no real observations or invented retrieval dates.
// Fake observations below are written exclusively to data/fixtures/.
const fields = {
  district_reference: ["999001", "Test District 01", "Test State", "test-district-999001", "[]"],
  rto_to_district: ["Test State", "XX01", "999001", "false", ""],
  ev_registrations: ["2020-01", "Test State", "XX01", "999001", "2W", "PURE EV", "12"],
  public_chargers: [
    "test-public-charger-01",
    "Test Station 01",
    "10",
    "75",
    "999001",
    "urban",
    "Type 2",
    "7.4",
    "AC",
    "",
    "Test source",
    "https://example.invalid/test-source",
    "2020-01-31",
  ],
  ev_tariffs: [
    "Test State",
    "Test DISCOM",
    "TEST-ORDER-01",
    "2020-01-01",
    "Test EV category",
    "100",
    "",
    "unknown",
    "",
    "Invented test rates; never publish",
  ],
} as const;
const integerFields = new Set([
  "lgd_code",
  "count",
  "energy_charge_paise_per_kwh",
  "demand_or_fixed_charge_paise",
]);
const numberFields = new Set(["lat", "lon", "power_kw"]);
function columns(id: (typeof datasetIds)[number]) {
  const names =
    id in rowSchemas
      ? Object.keys(rowSchemas[id as CsvDatasetId].shape)
      : id === "highways"
        ? ["osm_id", "ref", "road_class", "geometry"]
        : ["lgd_code", "geometry"];
  return names.map((name) => ({
    name,
    type: integerFields.has(name)
      ? "integer"
      : numberFields.has(name)
        ? "number"
        : name === "former_names" || name === "geometry"
          ? "json"
          : name === "covers_multiple_districts"
            ? "boolean"
            : name === "month" || name === "opened_month"
              ? "month"
              : name === "recorded_on" || name === "effective_from"
                ? "date"
                : "string",
    unit: name.includes("paise")
      ? name.includes("kwh")
        ? "paise/kWh"
        : "paise (basis in unit)"
      : name === "power_kw"
        ? "kW"
        : name === "count"
          ? "vehicles"
          : name === "lgd_code"
            ? "LGD district code"
            : name === "geometry" || name === "lat" || name === "lon"
              ? "EPSG:4326"
              : "not applicable",
    description: `Document the source definition of ${name}`,
    ...(["opened_month", "demand_or_fixed_charge_paise"].includes(name) ? { nullable: true } : {}),
  }));
}
const cell = (value: string) =>
  /[,"\r\n]/.test(value) ? `"${value.replaceAll('"', '""')}"` : value;
async function writeNew(path: string, value: string) {
  try {
    await access(path);
  } catch {
    await writeFile(path, value, "utf8");
  }
}
for (const id of datasetIds) {
  const publicDirectory = fileURLToPath(new URL(`../../data/public/${id}/`, import.meta.url));
  const fixtureDirectory = fileURLToPath(new URL(`../../data/fixtures/${id}/`, import.meta.url));
  await mkdir(publicDirectory, { recursive: true });
  await mkdir(fixtureDirectory, { recursive: true });
  const metadata = {
    id,
    title: `${id} — complete with sourced title`,
    description: "Complete with scope and definitions",
    source_name: "Complete with publisher",
    source_url: null,
    retrieved_on: null,
    licence: null,
    geography_level: id === "ev_tariffs" ? "state" : id === "highways" ? "corridor" : "district",
    time_coverage: "Complete with actual reporting period",
    update_frequency: "Complete with refresh schedule",
    notes: "Template only: not a retrieved or published dataset",
    columns: columns(id),
  };
  await writeNew(`${publicDirectory}meta.template.json`, JSON.stringify(metadata, null, 2) + "\n");
  const fixture = {
    ...metadata,
    title: `Test ${id}`,
    source_name: "Test source",
    source_url: "https://example.invalid/test-source",
    retrieved_on: "2020-01-31",
    licence: id === "highways" ? "ODbL-1.0 (test only)" : "CC0-1.0 (test only)",
    notes: "Invented test data. Never publish.",
    attribution: "Test attribution only",
    fixture: true,
  };
  await writeNew(`${fixtureDirectory}meta.json`, JSON.stringify(fixture, null, 2) + "\n");
  if (id in rowSchemas) {
    const header = Object.keys(rowSchemas[id as CsvDatasetId].shape).join(",");
    await writeNew(`${publicDirectory}data.template.csv`, header + "\n");
    await writeNew(
      `${fixtureDirectory}data.csv`,
      header + "\n" + fields[id as CsvDatasetId].map(cell).join(",") + "\n",
    );
  } else {
    const geometry =
      id === "highways"
        ? {
            type: "FeatureCollection",
            features: [
              {
                type: "Feature",
                properties: { osm_id: "test-osm-01", ref: "NH999", road_class: "national_highway" },
                geometry: {
                  type: "LineString",
                  coordinates: [
                    [75, 10],
                    [76, 10],
                  ],
                },
              },
            ],
          }
        : {
            type: "Topology",
            objects: {
              districts: {
                type: "GeometryCollection",
                geometries: [{ type: "Polygon", properties: { lgd_code: 999001 }, arcs: [[0]] }],
              },
            },
            arcs: [
              [
                [75, 10],
                [76, 10],
                [76, 11],
                [75, 11],
                [75, 10],
              ],
            ],
          };
    await writeNew(
      `${fixtureDirectory}${datasetFiles[id]}`,
      JSON.stringify(geometry, null, 2) + "\n",
    );
  }
}
console.log(
  "Public templates and clearly marked test fixtures prepared; existing files preserved.",
);
