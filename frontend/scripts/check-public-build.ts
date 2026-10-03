import { readFile, writeFile, readdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { parseCsv } from "./csv.ts";

const npmCli = process.env.npm_execpath;
if (!npmCli) throw new Error("Run this check with npm run data:check-build");
function refused(column: string) {
  const result = spawnSync(process.execPath, [npmCli!, "run", "build"], { encoding: "utf8" });
  const output = `${result.stdout}${result.stderr}`;
  if (result.status === 0 || !output.includes(`row 2, column ${column}:`))
    throw new Error(`Broken CSV did not produce the expected build refusal:\n${output}`);
}

// Acceptance: exercise the actual npm build gate, then restore the original
// bytes even if the command or assertion fails. Run without concurrent builds.
const reference = resolve("../data/public/district_reference/data.csv");
const original = await readFile(reference);
const broken = original.toString("utf8").replace(/(\r?\n)\d+,/, "$1-1,");
if (broken === original.toString("utf8"))
  throw new Error("No reference row available for build-refusal acceptance");
try {
  await writeFile(reference, broken, "utf8");
  // Running npm's JS entry avoids shell quoting and npm.cmd indirection.
  const result = spawnSync(process.execPath, [npmCli, "run", "build"], { encoding: "utf8" });
  const output = `${result.stdout}${result.stderr}`;
  if (result.status === 0 || !/data.csv: row 2, column lgd_code:/.test(output))
    throw new Error(`Broken CSV did not produce the expected build refusal:\n${output}`);
  console.log("PASS: npm run build refused district_reference/data.csv, row 2, column lgd_code.");
} finally {
  await writeFile(reference, original);
}

// Exercise every expansion schema through the actual npm build entry point.
// Pending sources use temporary synthetic files with an intentionally invalid
// row. Those files can never pass validation and are restored/removed in finally.
for (const [id, column, bad] of [
  ["discom_performance", "atc_loss_pct", "101"],
  ["supply_hours", "avg_supply_hours_per_day", "25"],
  ["state_ev_policies", "notified_on", "2020-02-30"],
  ["nhai_wayside_amenities", "lat", "91"],
  ["osm_power", "lon", "181"],
  ["cea_ev_consumption", "report_month", "2020-13"],
]) {
  const originals = new Map<string, Buffer | null>();
  const directory = resolve("../data/public", id!);
  try {
    for (const filename of ["meta.json", "data.csv"]) {
      const path = resolve(directory, filename);
      let original: Buffer | null;
      try {
        original = await readFile(path);
      } catch (error) {
        if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
        original = null;
      }
      originals.set(path, original);
      let source =
        original?.toString("utf8") ??
        (await readFile(resolve("../data/fixtures", id!, filename), "utf8"))
          .replaceAll('"fixture": true', '"fixture": false')
          .replaceAll("Test ", "Synthetic ")
          .replaceAll("example.invalid", "data.example.org");
      if (filename === "data.csv") {
        const records = parseCsv(source, path);
        if (!records[1]) throw new Error(`Build refusal needs a row for ${id}`);
        records[1].values[records[0]!.values.indexOf(column!)] = bad!;
        source =
          records
            .map((r) =>
              r.values
                .map((v) => (/[,"\r\n]/.test(v) ? `"${v.replaceAll('"', '""')}"` : v))
                .join(","),
            )
            .join("\n") + "\n";
      }
      await writeFile(path, source);
    }
    refused(column!);
    console.log(`PASS: npm run build refused ${id}/data.csv, row 2, column ${column}.`);
  } finally {
    for (const [path, bytes] of originals) {
      if (bytes === null) await rm(path, { force: true });
      else await writeFile(path, bytes);
    }
  }
}

async function scan(directory: string): Promise<void> {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) await scan(path);
    else if (/\.(?:html|json|js|map|csv|txt)$/.test(entry.name)) {
      const source = await readFile(path, "utf8");
      if (
        /Test Station 01|Test District 01|Test DISCOM|Test policy|test-wsa-01|test-public-charger-01|test-district-999001|example\.invalid\/test-source|Test District North|Test District South|example\.invalid\/chart-fixture|Chart development demo|District map development demo/.test(
          source,
        )
      )
        throw new Error(`Fixture observation found in production artifact: ${path}`);
    }
  }
}
await scan(resolve("dist"));
console.log(
  "PASS: production HTML, JS, source maps, catalogues and downloads contain no fixture observations.",
);
