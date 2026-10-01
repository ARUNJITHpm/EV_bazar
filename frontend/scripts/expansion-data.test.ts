// @vitest-environment node
import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { afterEach, expect, it } from "vitest";
import { expansionDatasetIds, rowSchemas } from "../src/features/analytics/data/schemas.ts";
import { loadPublicData, loadCsv } from "./public-data.ts";
import { parseCsv } from "./csv.ts";
import { exportPublicReference } from "./export-public-reference.ts";

const fixtures = fileURLToPath(new URL("../../data/fixtures", import.meta.url));
const temporary: string[] = [];
async function copy() {
  const root = await mkdtemp(resolve(tmpdir(), "chargeworthy-expansion-"));
  temporary.push(root);
  await cp(fixtures, root, { recursive: true });
  return root;
}
const cell = (s: string) => (/[,"\r\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s);
async function mutate(root: string, id: string, field: string, value: string) {
  const path = resolve(root, id, "data.csv");
  const records = parseCsv(await readFile(path, "utf8"), path);
  records[1]!.values[records[0]!.values.indexOf(field)] = value;
  await writeFile(path, records.map((r) => r.values.map(cell).join(",")).join("\n") + "\n");
}
afterEach(async () => {
  await Promise.all(temporary.splice(0).map((p) => rm(p, { recursive: true, force: true })));
});

it.each([
  ["discom_performance", "atc_loss_pct", "101"],
  ["supply_hours", "avg_supply_hours_per_day", "25"],
  ["state_ev_policies", "notified_on", "2020-02-30"],
  ["nhai_wayside_amenities", "lat", "91"],
  ["osm_power", "lon", "181"],
] as const)("refuses bad %s rows through the production build CLI", async (id, field, value) => {
  const root = await copy();
  // Isolated synthetic input; never copy these into data/public.
  for (const name of ["district_reference", id]) {
    for (const filename of ["meta.json", "data.csv"]) {
      const path = resolve(root, name, filename);
      const source = (await readFile(path, "utf8"))
        .replaceAll('"fixture": true', '"fixture": false')
        .replaceAll("Test ", "Synthetic ")
        .replaceAll("example.invalid", "data.example.org");
      await writeFile(path, source);
    }
  }
  for (const name of (await loadPublicData(fixtures, true)).catalogue.datasets.map((d) => d.id)) {
    if (name !== id && name !== "district_reference")
      await rm(resolve(root, name), { recursive: true });
  }
  await mutate(root, id, field, value);
  const result = spawnSync(
    process.execPath,
    [fileURLToPath(new URL("./validate-public-data.ts", import.meta.url)), "--root", root],
    { encoding: "utf8" },
  );
  expect(result.status).toBe(1);
  expect(result.stderr).toContain(`row 2, column ${field}:`);
});

it.each(expansionDatasetIds)("refuses duplicate natural keys for %s", async (id) => {
  const root = await copy();
  const path = resolve(root, id, "data.csv");
  const source = await readFile(path, "utf8");
  await writeFile(path, source + source.split("\n")[1] + "\n");
  await expect(loadPublicData(root, true)).rejects.toThrow(/duplicate observation/);
});

it("preserves missing grid/policy values and signed integer paise gaps", async () => {
  const loaded = await loadPublicData(fixtures, true);
  expect(loaded.reference.datasets.supply_hours!.rows[0]!.lgd_code).toBeNull();
  expect(loaded.reference.datasets.nhai_wayside_amenities!.rows[0]!.lat).toBeNull();
  expect(loaded.reference.datasets.state_ev_policies!.rows[0]!.valid_to).toBeNull();
  expect(loaded.reference.datasets.osm_power!.rows[0]!.voltage).toBeNull();
  expect(loaded.reference.datasets.discom_performance!.rows[0]!.acs_arr_gap_paise_per_kwh).toBe(
    -10,
  );
});

it.each([
  ["supply_hours", "period_type", "month", /complete calendar month/],
  ["supply_hours", "period_end", "2019-03-31", /precedes start/],
  ["supply_hours", "discom_id", "test-discom", /must be paired/],
  ["nhai_wayside_amenities", "lat", "10", /coordinates must be paired/],
  ["state_ev_policies", "valid_to", "2019-01-01", /precedes start/],
  ["osm_power", "point_derivation", "representative_point", /match point derivation/],
  ["osm_power", "lgd_code", "123456789", /absent from district_reference/],
  ["discom_performance", "fiscal_year", "2020-22", /invalid fiscal year/],
  ["discom_performance", "acs_arr_gap_paise_per_kwh", "1.2", /acs_arr_gap_paise_per_kwh/],
] as const)("refuses inconsistent %s %s", async (id, field, value, error) => {
  const root = await copy();
  await mutate(root, id, field, value);
  await expect(loadPublicData(root, true)).rejects.toThrow(error);
});

it.each(["licence_url", "source_sha256", "review_ref", "transformation_version"])(
  "requires expansion provenance %s",
  async (field) => {
    const root = await copy();
    const path = resolve(root, "supply_hours/meta.json");
    const meta = JSON.parse(await readFile(path, "utf8"));
    delete meta[field];
    await writeFile(path, JSON.stringify(meta));
    await expect(loadPublicData(root, true)).rejects.toThrow(field);
  },
);
it("retains ODbL and refuses unresolved licences", async () => {
  const root = await copy();
  const path = resolve(root, "osm_power/meta.json");
  const meta = JSON.parse(await readFile(path, "utf8"));
  meta.licence = "CC0";
  await writeFile(path, JSON.stringify(meta));
  await expect(loadPublicData(root, true)).rejects.toThrow(/ODbL/);
  meta.licence = "ODbL pending";
  await writeFile(path, JSON.stringify(meta));
  await expect(loadPublicData(root, true)).rejects.toThrow(/unresolved licence/);
});
it("refuses fixtures in offline backend export", async () => {
  const root = await copy();
  await expect(exportPublicReference(root, resolve(root, "snapshot.json"))).rejects.toThrow(
    /fixture dataset refused/,
  );
});
it("refuses an export path that could overwrite public inputs", async () => {
  const root = fileURLToPath(new URL("../../data/public", import.meta.url));
  const path = resolve(root, "district_reference/data.csv");
  const original = await readFile(path);
  await expect(exportPublicReference(root, path)).rejects.toThrow(/outside the public source root/);
  expect(await readFile(path)).toEqual(original);
});
it("allowlists expansion fields instead of copying private data", () => {
  const header = Object.keys(rowSchemas.supply_hours.shape).join(",") + ",owner_phone\n";
  expect(() => loadCsv("supply_hours", header, "private.csv")).toThrow(/unexpected column/);
});
