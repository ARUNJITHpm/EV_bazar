import { createHash } from "node:crypto";
import { readFile, readdir, realpath } from "node:fs/promises";
import { resolve, relative, isAbsolute } from "node:path";
import { z } from "zod";

import {
  datasetFiles,
  columnType,
  columnNullable,
  expansionDatasetIds,
  datasetIds,
  metadataSchema,
  publicDataVersions,
  rowSchemas,
  type CsvDatasetId,
  type DatasetId,
  type District,
  type PublicCatalogue,
} from "../src/features/analytics/data/schemas.ts";
import { parseCsv } from "./csv.ts";

export interface PublicArtifact {
  name: string;
  source: string;
}
export interface LoadedPublicData {
  catalogue: PublicCatalogue;
  artifacts: PublicArtifact[];
  reference: {
    catalogue: PublicCatalogue;
    fixture: boolean;
    datasets: Record<
      string,
      { rows: Row[]; metadata: unknown; raw_sha256: string; metadata_sha256: string }
    >;
  };
}
type Row = Record<string, unknown>;
function fail(file: string, row: number, column: string, message: string): never {
  throw new Error(`${file}: row ${row}, column ${column}: ${message}`);
}

async function safeRead(root: string, path: string): Promise<string> {
  // Refuse symlinks pointing at private/fixture trees even when located
  // under public/. Files are read once and only validated bytes are emitted.
  let target: string;
  try {
    target = await realpath(path);
  } catch {
    return fail(path, 1, "file", "required file is missing");
  }
  const within = relative(await realpath(root), target);
  if (within.startsWith("..") || isAbsolute(within))
    fail(path, 1, "file", "file must stay inside the public data root");
  return readFile(target, "utf8");
}

function validated<S extends z.ZodTypeAny>(
  schema: S,
  value: unknown,
  file: string,
  row: number,
): z.output<S> {
  const result = schema.safeParse(value);
  if (!result.success) {
    const issue = result.error.issues[0]!;
    fail(file, row, issue.path.join(".") || "schema", issue.message);
  }
  return result.data;
}

function json(source: string, file: string): unknown {
  try {
    return JSON.parse(source) as unknown;
  } catch {
    return fail(file, 1, "JSON", "invalid JSON document");
  }
}

export function loadCsv(
  id: CsvDatasetId,
  source: string,
  file: string,
): { rows: Row[]; lines: number[] } {
  const records = parseCsv(source, file);
  const header = records.shift();
  if (!header) fail(file, 1, "header", "CSV is empty");
  const expected = Object.keys(rowSchemas[id].shape);
  for (const column of expected)
    if (!header.values.includes(column)) fail(file, 1, column, "required column is missing");
  if (new Set(header.values).size !== header.values.length)
    fail(file, 1, "header", "duplicate column name");
  for (const column of header.values)
    if (!expected.includes(column))
      fail(file, 1, column, "unexpected column; public fields are allowlisted");
  const rows: Row[] = [],
    lines: number[] = [];
  for (const record of records) {
    if (record.values.length !== header.values.length)
      fail(file, record.row, "record", "wrong number of CSV cells");
    const raw = Object.fromEntries(
      header.values.map((name, index) => [name, record.values[index]!]),
    );
    rows.push(validated(rowSchemas[id], raw, file, record.row));
    lines.push(record.row);
  }
  return { rows, lines };
}

const coordinate = z.tuple([
  z.number().finite().min(-180).max(180),
  z.number().finite().min(-90).max(90),
]);
const line = z.array(coordinate).min(2);
const roadProperties = z
  .object({
    osm_id: z.string().min(1),
    ref: z.string().regex(/^NH[ -]?\d+[A-Z]?$/),
    road_class: z.literal("national_highway"),
  })
  .strict();
const highwaySchema = z
  .object({
    type: z.literal("FeatureCollection"),
    features: z.array(
      z
        .object({
          type: z.literal("Feature"),
          properties: roadProperties,
          geometry: z.union([
            z.object({ type: z.literal("LineString"), coordinates: line }).strict(),
            z
              .object({ type: z.literal("MultiLineString"), coordinates: z.array(line).min(1) })
              .strict(),
          ]),
        })
        .strict(),
    ),
  })
  .strict();
const polygonSchema = z
  .object({
    type: z.enum(["Polygon", "MultiPolygon"]),
    properties: z.object({ lgd_code: z.number().int().positive() }).strict(),
    arcs: z.unknown(),
  })
  .strict();
const topologySchema = z
  .object({
    type: z.literal("Topology"),
    transform: z
      .object({
        scale: z.tuple([z.number().positive(), z.number().positive()]),
        translate: coordinate,
      })
      .strict()
      .optional(),
    objects: z
      .object({
        districts: z
          .object({ type: z.literal("GeometryCollection"), geometries: z.array(polygonSchema) })
          .strict(),
      })
      .strict(),
    arcs: z.array(z.array(z.tuple([z.number().finite(), z.number().finite()])).min(2)),
  })
  .strict();

function geometryRows(id: DatasetId, source: string, file: string): Row[] {
  const value = json(source, file);
  if (id === "highways")
    return validated(highwaySchema, value, file, 1).features.map(({ properties }) => properties);
  const topology = validated(topologySchema, value, file, 1);
  const decodedArcs = topology.arcs.map((arc, arcIndex) => {
    let x = 0,
      y = 0;
    return arc.map((pair) => {
      if (topology.transform) {
        if (!pair.every(Number.isSafeInteger))
          fail(file, arcIndex + 1, "arcs", "quantized deltas must be integers");
        x += pair[0];
        y += pair[1];
        return validated(
          coordinate,
          [
            x * topology.transform.scale[0] + topology.transform.translate[0],
            y * topology.transform.scale[1] + topology.transform.translate[1],
          ],
          file,
          arcIndex + 1,
        );
      } else return validated(coordinate, pair, file, arcIndex + 1);
    });
  });
  function ring(value: unknown, row: number) {
    const refs = validated(
      z.array(z.number().int().refine(Number.isSafeInteger)).min(1),
      value,
      file,
      row,
    );
    const vertices: [number, number][] = [];
    for (const ref of refs) {
      const index = ref < 0 ? -(ref + 1) : ref;
      if (index >= topology.arcs.length) fail(file, row, "arcs", "reference does not exist");
      const arc = ref < 0 ? [...decodedArcs[index]!].reverse() : decodedArcs[index]!;
      const last = vertices.at(-1);
      if (last && (last[0] !== arc[0]![0] || last[1] !== arc[0]![1]))
        fail(file, row, "arcs", "ring arcs do not connect");
      vertices.push(...(last ? arc.slice(1) : arc));
    }
    if (
      vertices.length < 4 ||
      vertices[0]![0] !== vertices.at(-1)![0] ||
      vertices[0]![1] !== vertices.at(-1)![1]
    )
      fail(file, row, "arcs", "polygon ring must be closed with at least four vertices");
  }
  topology.objects.districts.geometries.forEach((geometry, index) => {
    const polygons =
      geometry.type === "Polygon"
        ? [geometry.arcs]
        : validated(z.array(z.unknown()).min(1), geometry.arcs, file, index + 1);
    for (const polygon of polygons)
      for (const value of validated(z.array(z.unknown()).min(1), polygon, file, index + 1))
        ring(value, index + 1);
  });
  return topology.objects.districts.geometries.map(({ properties }) => properties);
}

export async function loadPublicData(root: string, fixtures = false): Promise<LoadedPublicData> {
  const catalogue: PublicCatalogue = {
    versions: publicDataVersions,
    districts: [],
    datasets: [],
    pending: [],
  };
  const artifacts: PublicArtifact[] = [];
  const snapshot: LoadedPublicData["reference"] = { catalogue, fixture: fixtures, datasets: {} };
  const rowsById = new Map<DatasetId, { rows: Row[]; lines: number[]; file: string }>();
  let entries;
  try {
    entries = await readdir(root, { withFileTypes: true });
  } catch {
    return fail(root, 1, "directory", "public data root is missing");
  }
  for (const entry of entries)
    if (
      (entry.isDirectory() || entry.isSymbolicLink()) &&
      !datasetIds.includes(entry.name as DatasetId)
    )
      fail(root, 1, entry.name, "unknown public dataset directory");
  for (const id of datasetIds) {
    const directory = resolve(root, id),
      file = resolve(directory, datasetFiles[id]),
      metaFile = resolve(directory, "meta.json");
    let names: string[];
    try {
      names = await readdir(directory);
    } catch {
      catalogue.pending.push(id);
      continue;
    }
    const active = names.includes("meta.json") || names.includes(datasetFiles[id]);
    if (!active) {
      if (
        names.some(
          (name) => ![".gitkeep", "meta.template.json", "data.template.csv"].includes(name),
        )
      )
        fail(directory, 1, "file", "unexpected file in pending dataset");
      catalogue.pending.push(id);
      continue;
    }
    for (const name of names)
      if (
        ![
          "meta.json",
          datasetFiles[id],
          ".gitkeep",
          "meta.template.json",
          "data.template.csv",
        ].includes(name)
      )
        fail(directory, 1, name, "unreviewed file in public dataset");
    const metaSource = await safeRead(root, metaFile);
    const meta = validated(metadataSchema, json(metaSource, metaFile), metaFile, 1);
    if (meta.id !== id) fail(metaFile, 1, "id", "must match dataset directory");
    if (Boolean(meta.fixture) !== fixtures)
      fail(
        metaFile,
        1,
        "fixture",
        fixtures
          ? "test metadata must declare fixture: true"
          : "fixture dataset refused in production",
      );
    const source = await safeRead(root, file);
    if (
      !fixtures &&
      /\bTest (?:Station|District|State)\b|example\.invalid/i.test(source + metaSource)
    )
      fail(file, 1, "fixture", "test markers refused in public data");
    const isCsv = id in rowSchemas;
    const loaded = isCsv
      ? loadCsv(id as CsvDatasetId, source, file)
      : { rows: geometryRows(id, source, file), lines: [] };
    const expected = isCsv
      ? Object.keys(rowSchemas[id as CsvDatasetId].shape)
      : id === "highways"
        ? ["osm_id", "ref", "road_class", "geometry"]
        : ["lgd_code", "geometry"];
    const columns = meta.columns.map(({ name }) => name);
    if (new Set(columns).size !== columns.length)
      fail(metaFile, 1, "columns", "duplicate metadata column");
    for (const column of expected)
      if (!columns.includes(column))
        fail(metaFile, 1, `columns.${column}`, "column description is missing");
    for (const column of columns)
      if (!expected.includes(column))
        fail(metaFile, 1, `columns.${column}`, "unexpected metadata column");
    for (const column of meta.columns) {
      const name = column.name;
      const type = columnType(name);
      if (column.type !== type) fail(metaFile, 1, `columns.${name}.type`, `must be ${type}`);
      if (
        expansionDatasetIds.includes(id as (typeof expansionDatasetIds)[number]) &&
        Boolean(column.nullable) !== columnNullable(id, name)
      )
        fail(metaFile, 1, `columns.${name}.nullable`, "must match the row schema");
      if (name.includes("paise") && !column.unit.startsWith("paise"))
        fail(metaFile, 1, `columns.${name}.unit`, "money must be documented in paise");
    }
    if (["highways", "osm_power"].includes(id) && !meta.licence.includes("ODbL"))
      fail(metaFile, 1, "licence", "OSM highways must retain ODbL attribution");
    if (["highways", "district_boundaries", "osm_power"].includes(id) && !meta.attribution)
      fail(metaFile, 1, "attribution", "geometry requires explicit attribution");
    if (expansionDatasetIds.includes(id as (typeof expansionDatasetIds)[number])) {
      for (const field of [
        "source_sha256",
        "licence_url",
        "review_ref",
        "transformation_version",
      ] as const)
        if (!meta[field]) fail(metaFile, 1, field, "expansion sources require verified provenance");
      if (/pending|unknown|template/i.test(meta.licence))
        fail(metaFile, 1, "licence", "unresolved licence cannot activate a dataset");
    }
    snapshot.datasets[id] = {
      rows: loaded.rows,
      metadata: meta,
      raw_sha256: createHash("sha256").update(source).digest("hex"),
      metadata_sha256: createHash("sha256").update(metaSource).digest("hex"),
    };
    rowsById.set(id, { ...loaded, file });
    const prefix = `analytics-data/${id}`;
    const exported = isCsv
      ? `# Chargeworthy Data: ${JSON.stringify({ original_content_licence: "CC BY 4.0", licence_url: "https://creativecommons.org/licenses/by/4.0/", source_name: meta.source_name, source_url: meta.source_url, source_data_licence: meta.licence, attribution: meta.attribution ?? meta.source_name, notes: "Third-party data retains its own licence; CC BY 4.0 applies only to original Chargeworthy content." })}\r\n${source}`
      : source;
    const sha256 = createHash("sha256").update(exported).digest("hex");
    catalogue.datasets.push({
      id,
      metadata: meta,
      rows: loaded.rows.length,
      data_url: `/${prefix}/${datasetFiles[id]}`,
      sha256,
    });
    artifacts.push(
      { name: `${prefix}/${datasetFiles[id]}`, source: exported },
      {
        name: `${prefix}/meta.json`,
        source: JSON.stringify(
          { ...meta, artifact_sha256: sha256, versions: publicDataVersions },
          null,
          2,
        ),
      },
      {
        name: `${prefix}/README.txt`,
        source: `${meta.title}\nSource: ${meta.source_name}\n${meta.source_url}\nRetrieved: ${meta.retrieved_on}\nLicence: ${meta.licence}\n${meta.licence_url ?? ""}\n${meta.attribution ?? ""}\n${meta.notes}\nOriginal Chargeworthy content: CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/).\nCredit Chargeworthy Data and the original source; identify changes.\nThird-party data retains its source licence.\n`,
      },
    );
  }
  const reference = rowsById.get("district_reference");
  const districts = reference?.rows as District[] | undefined;
  const byCode = new Map<number, District>();
  const slugs = new Set<string>();
  for (const [index, district] of (districts ?? []).entries()) {
    if (byCode.has(district.lgd_code) || slugs.has(district.slug))
      fail(
        reference!.file,
        reference!.lines[index]!,
        "lgd_code/slug",
        "district code and slug must each be unique",
      );
    byCode.set(district.lgd_code, district);
    slugs.add(district.slug);
  }
  catalogue.districts = districts ?? [];
  for (const [id, loaded] of rowsById) {
    const seen = new Set<string>();
    for (const [index, row] of loaded.rows.entries()) {
      const line = loaded.lines[index] ?? index + 1;
      if ("lgd_code" in row && row.lgd_code !== null) {
        const district = byCode.get(row.lgd_code as number);
        if (!district)
          fail(loaded.file, line, "lgd_code", "code is absent from district_reference");
        if ("state" in row && row.state !== district.state_name)
          fail(loaded.file, line, "state", "does not match district reference");
      }
      let key: string | undefined;
      if (id === "public_chargers") key = String(row.charger_id);
      if (id === "ev_registrations") {
        key = JSON.stringify([
          row.month,
          row.state,
          row.rto_code,
          row.lgd_code,
          row.vehicle_class,
          row.fuel,
        ]);
        const mapping = rowsById
          .get("rto_to_district")
          ?.rows.find(
            (mapping) =>
              mapping.rto_code === row.rto_code &&
              mapping.state === row.state &&
              mapping.lgd_code === row.lgd_code,
          );
        if (!mapping)
          fail(loaded.file, line, "rto_code", "verified RTO-to-district mapping is required");
        if (mapping.covers_multiple_districts && !String(mapping.allocation_note).trim())
          fail(loaded.file, line, "rto_code", "multi-district RTO needs an allocation note");
      }
      if (id === "rto_to_district") {
        key = JSON.stringify([row.state, row.rto_code, row.lgd_code]);
        const siblings = loaded.rows.filter(
          (other) => other.state === row.state && other.rto_code === row.rto_code,
        );
        if (siblings.length > 1 && !row.covers_multiple_districts)
          fail(loaded.file, line, "covers_multiple_districts", "RTO has several mapped districts");
        if (row.covers_multiple_districts && !String(row.allocation_note).trim())
          fail(loaded.file, line, "allocation_note", "multi-district coverage must be explained");
      }
      if (id === "ev_tariffs") {
        if (row.unit === "none" && row.demand_or_fixed_charge_paise !== 0)
          fail(
            loaded.file,
            line,
            "unit",
            "a verified nil charge must be zero; missing amounts are unknown",
          );
        if (row.unit !== "unknown" && row.demand_or_fixed_charge_paise === null)
          fail(
            loaded.file,
            line,
            "demand_or_fixed_charge_paise",
            "charge basis requires a known amount",
          );
        if (row.unit === "unknown" && row.demand_or_fixed_charge_paise !== null)
          fail(loaded.file, line, "unit", "unknown basis requires a missing amount");
        if (!catalogue.districts.some((district) => district.state_name === row.state))
          fail(loaded.file, line, "state", "state is absent from district reference");
      }

      if (expansionDatasetIds.includes(id as (typeof expansionDatasetIds)[number])) {
        if (
          "state" in row &&
          !(id === "state_ev_policies" && row.state === "central") &&
          !(id === "discom_performance" && row.state === "India" && row.discom_id === "national") &&
          !catalogue.districts.some((d) => d.state_name === row.state)
        )
          fail(loaded.file, line, "state", "state is absent from district reference");
        if (
          id === "discom_performance" &&
          (row.state === "India") !== (row.discom_id === "national")
        )
          fail(
            loaded.file,
            line,
            "discom_id",
            "national reference must use state India and discom_id national together",
          );
        if (id === "discom_performance")
          key = JSON.stringify([
            row.discom_id,
            row.fiscal_year,
            row.metric_basis,
            row.source_edition,
          ]);
        if (id === "supply_hours") {
          if (String(row.period_start) > String(row.period_end))
            fail(loaded.file, line, "period_end", "period end precedes start");
          if ((row.discom_id === null) !== (row.discom === null))
            fail(loaded.file, line, "discom_id", "utility ID and name must be paired");
          const start = String(row.period_start),
            end = String(row.period_end);
          const year = Number(start.slice(0, 4));
          const endOfMonth = new Date(Date.UTC(year, Number(start.slice(5, 7)), 0))
            .toISOString()
            .slice(0, 10);
          if (row.period_type === "month" && (start.slice(8) !== "01" || end !== endOfMonth))
            fail(loaded.file, line, "period_type", "month must cover one complete calendar month");
          if (
            row.period_type === "fiscal_year" &&
            (start !== `${year}-04-01` || end !== `${year + 1}-03-31`)
          )
            fail(loaded.file, line, "period_type", "fiscal year must be April-March");
          if (
            row.period_type === "calendar_year" &&
            (start !== `${year}-01-01` || end !== `${year}-12-31`)
          )
            fail(loaded.file, line, "period_type", "calendar year must be January-December");
          key = JSON.stringify([
            row.state,
            row.discom_id,
            row.lgd_code,
            row.period_start,
            row.period_end,
            row.area_type,
            row.supply_definition,
          ]);
        }
        if (id === "state_ev_policies") {
          if (row.valid_to !== null && String(row.valid_to) < String(row.valid_from))
            fail(loaded.file, line, "valid_to", "validity end precedes start");
          key = JSON.stringify([
            row.state,
            row.notification_ref,
            row.clause_ref,
            row.incentive_type,
            row.vehicle_scope,
            row.valid_from,
          ]);
        }
        if (id === "nhai_wayside_amenities") {
          if ((row.lat === null) !== (row.lon === null))
            fail(loaded.file, line, "lat/lon", "coordinates must be paired or both unknown");
          key = JSON.stringify([row.wsa_id, row.source_doc_date, row.status_as_of, row.status]);
        }
        if (id === "osm_power") {
          if (String(row.osm_id).startsWith("node/") !== (row.point_derivation === "node"))
            fail(loaded.file, line, "point_derivation", "object type must match point derivation");
          key = JSON.stringify([row.osm_id, row.extract_date]);
        }
      }
      if (id === "district_boundaries") key = String(row.lgd_code);
      if (key !== undefined && seen.has(key))
        fail(loaded.file, line, "key", "duplicate observation; resolve before publication");
      if (key !== undefined) seen.add(key);
    }
  }
  // Geometry is emitted as a separate asset, never bundled into route JS.
  artifacts.push({
    name: "analytics-data/catalogue.json",
    source: JSON.stringify(catalogue, null, 2),
  });
  return { catalogue, artifacts, reference: snapshot };
}
