import { readFile, readdir, realpath } from "node:fs/promises";
import { resolve, relative, isAbsolute } from "node:path";
import { parseCsv } from "./csv.ts";
import {
  usageRowSchema,
  usageBaseSchema,
  usageMetaSchema,
  type UsageRow,
  type UsageMeta,
} from "../src/features/analytics/data/usage.ts";
import type { PublicCatalogue } from "../src/features/analytics/data/schemas.ts";
export async function loadPublishedUsage(
  root: string,
  catalogue: PublicCatalogue,
): Promise<{
  rows: UsageRow[];
  metadata: UsageMeta | null;
  artifacts: { name: string; source: string }[];
}> {
  let names: string[];
  try {
    names = await readdir(root);
  } catch {
    return { rows: [], metadata: null, artifacts: [] };
  }
  if (names.some((name) => ![".gitkeep", "usage_estimates.csv", "meta.json"].includes(name)))
    throw new Error("Published usage contains unreviewed files");
  if (!names.includes("usage_estimates.csv") && !names.includes("meta.json"))
    return { rows: [], metadata: null, artifacts: [] };
  async function safe(name: string) {
    const path = await realpath(resolve(root, name));
    const within = relative(resolve(root), path);
    if (within.startsWith("..") || isAbsolute(within))
      throw new Error("Published usage symlink escapes approved root");
    return readFile(path, "utf8");
  }
  const csv = await safe("usage_estimates.csv"),
    meta = await safe("meta.json");
  if (/Test (?:Station|District|State)|example\.invalid|test-public/i.test(csv + meta))
    throw new Error("Fixture usage cannot be published");
  const metadata = usageMetaSchema.parse(JSON.parse(meta));
  for (const id of ["public_chargers", "ev_registrations"] as const)
    if (
      catalogue.datasets.find((dataset) => dataset.id === id)?.sha256 !== metadata.source_hashes[id]
    )
      throw new Error("Published usage source hashes differ from the validated public build");
  const parsed = parseCsv(csv, "usage_estimates.csv"),
    header = parsed.shift()!.values;
  const expected = Object.keys(usageBaseSchema.shape);
  if (
    header.length !== expected.length ||
    new Set(header).size !== expected.length ||
    expected.some((key) => !header.includes(key))
  )
    throw new Error("Published usage CSV must contain only aggregate allowlisted fields");
  const seen = new Set<string>();
  const rows = parsed.map(({ values, row }) => {
    if (values.length !== header.length)
      throw new Error(`usage_estimates.csv: row ${row}: unexpected cells`);
    const result = usageRowSchema.safeParse(
      Object.fromEntries(header.map((name, index) => [name, values[index]])),
    );
    if (!result.success)
      throw new Error(`usage_estimates.csv: row ${row}: ${result.error.issues[0]?.message}`);
    const key = `${result.data.lgd_code}:${result.data.month}`;
    if (
      seen.has(key) ||
      !catalogue.districts.some((district) => district.lgd_code === result.data.lgd_code)
    )
      throw new Error(`usage_estimates.csv: row ${row}: duplicate or unknown district`);
    seen.add(key);
    return result.data;
  });
  return {
    rows,
    metadata,
    artifacts: [
      { name: "analytics-data/usage_estimates/data.csv", source: csv },
      { name: "analytics-data/usage_estimates/meta.json", source: meta },
    ],
  };
}
