import { mkdir, writeFile, access } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import {
  datasetFiles,
  columnType,
  columnNullable,
  expansionDatasetIds,
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

  discom_performance: [
    "Test State",
    "test-discom",
    "Test DISCOM",
    "2020-21",
    "12.5",
    "-10",
    "Test accrual basis",
    "Test edition",
    "Test table p1",
    "Invented",
  ],
  supply_hours: [
    "Test State",
    "",
    "",
    "",
    "fiscal_year",
    "2020-04-01",
    "2021-03-31",
    "2020-21",
    "rural",
    "20.5",
    "Test annual feeder average",
    "Test source",
    "https://example.invalid/test-source",
    "2021-04-30",
    "Invented",
  ],
  state_ev_policies: [
    "Test State",
    "Test policy",
    "TEST-GO",
    "Test clause 1",
    "2020-01-01",
    "2020-01-01",
    "",
    "charging_capex_subsidy",
    "charging",
    "",
    "Test eligibility",
    "",
    "https://example.invalid/test-source",
    "2020-01-31",
    "Invented",
  ],
  nhai_wayside_amenities: [
    "test-wsa-01",
    "NH999",
    "Test State",
    "",
    "12",
    "",
    "",
    "Test historical announced",
    "",
    "unknown",
    "",
    "Test page 1",
    "Invented",
  ],
  osm_power: ["node/999999999", "transformer", "", "10", "75", "999001", "2020-01-31", "node"],
} as const;
function columns(id: (typeof datasetIds)[number]) {
  const names =
    id in rowSchemas
      ? Object.keys(rowSchemas[id as CsvDatasetId].shape)
      : id === "highways"
        ? ["osm_id", "ref", "road_class", "geometry"]
        : ["lgd_code", "geometry"];
  return names.map((name) => ({
    name,
    type: columnType(name),
    unit: name.includes("paise")
      ? name.includes("kwh")
        ? "paise/kWh"
        : "paise (basis in unit)"
      : name === "atc_loss_pct"
        ? "percent"
        : name === "avg_supply_hours_per_day"
          ? "hours/day"
          : name === "chainage_km"
            ? "km"
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
    ...(columnNullable(id, name) ? { nullable: true } : {}),
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
    geography_level:
      id === "discom_performance"
        ? "discom"
        : ["supply_hours", "nhai_wayside_amenities"].includes(id)
          ? "mixed"
          : ["ev_tariffs", "state_ev_policies"].includes(id)
            ? "state"
            : id === "highways"
              ? "corridor"
              : "district",
    time_coverage: "Complete with actual reporting period",
    update_frequency: "Complete with refresh schedule",
    notes: "Template only: not a retrieved or published dataset",
    columns: columns(id),
    ...(expansionDatasetIds.includes(id as (typeof expansionDatasetIds)[number])
      ? { source_sha256: null, licence_url: null, review_ref: null, transformation_version: null }
      : {}),
  };
  await writeNew(`${publicDirectory}meta.template.json`, JSON.stringify(metadata, null, 2) + "\n");
  const fixture = {
    ...metadata,
    title: `Test ${id}`,
    source_name: "Test source",
    source_url: "https://example.invalid/test-source",
    retrieved_on: "2020-01-31",
    licence: ["highways", "osm_power"].includes(id)
      ? "ODbL-1.0 (test only)"
      : "CC0-1.0 (test only)",
    notes: "Invented test data. Never publish.",
    attribution: "Test attribution only",
    fixture: true,
    source_sha256: "0".repeat(64),
    licence_url: "https://example.invalid/test-licence",
    review_ref: "Test human review",
    transformation_version: "test-v1",
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
