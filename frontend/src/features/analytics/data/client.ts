import { z } from "zod";
import catalogue from "virtual:analytics-public-data";
import { rowSchemas, type CsvDatasetId, type DatasetId } from "./schemas";
import { parseCsv } from "../../../../scripts/csv";

export { catalogue as publicCatalogue };

export async function loadPublicCsv<T extends CsvDatasetId>(
  id: T,
): Promise<z.output<(typeof rowSchemas)[T]>[] | null> {
  const dataset = catalogue.datasets.find((dataset) => dataset.id === id);
  if (!dataset) return null;
  const response = await fetch(dataset.data_url);
  if (!response.ok) throw new Error(`Public dataset ${id} could not be loaded`);
  const csv = await response.text();
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(csv));
  const sha = Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join(
    "",
  );
  if (sha !== dataset.sha256)
    throw new Error(`Public dataset ${id} differs from its validated build`);
  const records = parseCsv(csv, dataset.data_url);
  const header = records.shift();
  if (!header) throw new Error(`Public dataset ${id} has no header`);
  return records.map(
    ({ values }) =>
      rowSchemas[id].parse(
        Object.fromEntries(header.values.map((column, index) => [column, values[index]])),
      ) as z.output<(typeof rowSchemas)[T]>,
  );
}

export function datasetDescriptor(id: DatasetId) {
  return catalogue.datasets.find((dataset) => dataset.id === id) ?? null;
}

export async function developmentFixtures(search: string) {
  if (!import.meta.env.DEV || new URLSearchParams(search).get("fixtures") !== "1") return null;
  return (await import("virtual:analytics-fixtures")).default;
}
