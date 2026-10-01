// @vitest-environment node
import { cp, mkdtemp, readFile, rm, writeFile, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { afterEach, describe, expect, it } from "vitest";
import { loadCsv, loadPublicData } from "./public-data";
import { parseCsv } from "./csv";

const fixtureRoot = fileURLToPath(new URL("../../data/fixtures", import.meta.url));
const publicRoot = fileURLToPath(new URL("../../data/public", import.meta.url));
const temporary: string[] = [];
async function copy(root = fixtureRoot) {
  const directory = await mkdtemp(resolve(tmpdir(), "chargeworthy-public-data-"));
  temporary.push(directory);
  await cp(root, directory, { recursive: true });
  return directory;
}
async function change(root: string, file: string, mutate: (source: string) => string) {
  const path = resolve(root, file);
  await writeFile(path, mutate(await readFile(path, "utf8")), "utf8");
}
afterEach(async () => {
  await Promise.all(
    temporary.splice(0).map((directory) => rm(directory, { recursive: true, force: true })),
  );
});

describe("CSV grammar and diagnostics", () => {
  it("skips the reserved licence preamble without losing BOM support or row diagnostics", () => {
    expect(
      parseCsv(
        '# Chargeworthy Data: {"licence":"CC BY 4.0"}\r\n\uFEFFname,count\r\nx,1\r\n',
        "licensed.csv",
      ),
    ).toEqual([
      { row: 2, values: ["name", "count"] },
      { row: 3, values: ["x", "1"] },
    ]);
    expect(() => parseCsv('# Chargeworthy Data: {}\nname\n"unfinished', "licensed.csv")).toThrow(
      /row 3/,
    );
  });
  it("reads BOM, escaped quotes, CRLF and embedded lines without splitting a quoted field", () => {
    expect(
      parseCsv('\uFEFFname,note\r\n"Test Station 01","one, ""two""\nthree"\r\n', "sample.csv"),
    ).toEqual([
      { row: 1, values: ["name", "note"] },
      { row: 2, values: ["Test Station 01", 'one, "two"\nthree'] },
    ]);
  });
  it("refuses malformed quotes with file, row and column", () => {
    expect(() => parseCsv('a,b\n"unfinished', "broken.csv")).toThrow(
      /broken.csv: row 2, column 1: unterminated/,
    );
  });
  it("rejects unexpected private columns instead of copying them", () => {
    expect(() =>
      loadCsv(
        "district_reference",
        "lgd_code,district_name,state_name,slug,former_names,owner_phone\n",
        "private.csv",
      ),
    ).toThrow(/row 1, column owner_phone: unexpected column/);
  });
});

describe("public data gate", () => {
  it("validates every fixture schema including geometry and retains missing values as null", async () => {
    const { catalogue } = await loadPublicData(fixtureRoot, true);
    expect(catalogue.datasets).toHaveLength(12);
    expect(catalogue.pending).toEqual([]);
    const charger = loadCsv(
      "public_chargers",
      await readFile(resolve(fixtureRoot, "public_chargers/data.csv"), "utf8"),
      "fixture.csv",
    ).rows[0]!;
    expect(charger.opened_month).toBeNull();
    const tariff = loadCsv(
      "ev_tariffs",
      await readFile(resolve(fixtureRoot, "ev_tariffs/data.csv"), "utf8"),
      "fixture.csv",
    ).rows[0]!;
    expect(tariff.demand_or_fixed_charge_paise).toBeNull();
    expect(tariff.unit).toBe("unknown");
  });
  it("refuses the fixture tree in a production validation", async () => {
    await expect(loadPublicData(fixtureRoot)).rejects.toThrow(
      /meta.json: row 1, column fixture: fixture dataset refused/,
    );
  });
  it("also refuses test markers with fixture flags removed", async () => {
    const root = await copy();
    await change(root, "district_reference/meta.json", (source) =>
      source.replace('"fixture": true', '"fixture": false'),
    );
    await expect(loadPublicData(root)).rejects.toThrow(/column fixture: test markers refused/);
  });
  it("fails on a negative count at the correct CSV row and column", async () => {
    const root = await copy();
    await change(root, "ev_registrations/data.csv", (source) =>
      source.replace(/,12(\r?\n)/, ",-12$1"),
    );
    await expect(loadPublicData(root, true)).rejects.toThrow(
      /ev_registrations[/\\]data.csv: row 2, column count:/,
    );
  });
  it("does not accept empty required values as zero", async () => {
    const root = await copy();
    await change(root, "ev_registrations/data.csv", (source) =>
      source.replace(/,12(\r?\n)/, ",$1"),
    );
    await expect(loadPublicData(root, true)).rejects.toThrow(/column count:/);
  });
  it.each(["2020-02-30", "not-a-date"])("rejects invalid retrieval date %s", async (date) => {
    const root = await copy();
    await change(root, "ev_registrations/meta.json", (source) =>
      source.replace('"retrieved_on": "2020-01-31"', `"retrieved_on": "${date}"`),
    );
    await expect(loadPublicData(root, true)).rejects.toThrow(/column retrieved_on:/);
  });
  it("requires a source URL and metadata for every active dataset", async () => {
    const root = await copy();
    await rm(resolve(root, "public_chargers/meta.json"));
    await expect(loadPublicData(root, true)).rejects.toThrow(
      /public_chargers[/\\]meta.json: row 1, column file: required file is missing/,
    );
  });
  it("rejects unsourced active data, even when other datasets remain pending", async () => {
    const root = await copy(publicRoot);
    await writeFile(resolve(root, "ev_registrations/data.csv"), "month\n2020-01\n");
    await expect(loadPublicData(root)).rejects.toThrow(
      /ev_registrations[/\\]meta.json: row 1, column file/,
    );
  });
  it("rejects unknown LGD codes", async () => {
    const root = await copy();
    await change(root, "public_chargers/data.csv", (source) =>
      source.replace(",999001,", ",999002,"),
    );
    await expect(loadPublicData(root, true)).rejects.toThrow(
      /row 2, column lgd_code: code is absent/,
    );
  });
  it("requires verified RTO mappings for registration rows", async () => {
    const root = await copy();
    await change(root, "ev_registrations/data.csv", (source) => source.replace(",XX01,", ",XX02,"));
    await expect(loadPublicData(root, true)).rejects.toThrow(/column rto_code: verified RTO/);
  });
  it("requires an allocation note for multi-district RTOs", async () => {
    const root = await copy();
    await change(root, "rto_to_district/data.csv", (source) => source.replace(",false,", ",true,"));
    await expect(loadPublicData(root, true)).rejects.toThrow(/allocation/);
  });
  it("rejects duplicate physical charger IDs instead of double counting", async () => {
    const root = await copy();
    await change(
      root,
      "public_chargers/data.csv",
      (source) => source + source.split("\n")[1] + "\n",
    );
    await expect(loadPublicData(root, true)).rejects.toThrow(
      /row 3, column key: duplicate observation/,
    );
  });
  it("keeps unknown fixed charges distinct from a verified nil charge", async () => {
    const root = await copy();
    await change(root, "ev_tariffs/data.csv", (source) => source.replace(",unknown,", ",none,"));
    await expect(loadPublicData(root, true)).rejects.toThrow(/column unit: a verified nil charge/);
  });
  it("rejects broken TopoJSON references", async () => {
    const root = await copy();
    await change(root, "district_boundaries/data.topojson", (source) => {
      const topology = JSON.parse(source);
      topology.objects.districts.geometries[0].arcs = [[5]];
      return JSON.stringify(topology);
    });
    await expect(loadPublicData(root, true)).rejects.toThrow(
      /column arcs: reference does not exist/,
    );
  });
  it("rejects highway geometry with out-of-range longitude", async () => {
    const root = await copy();
    await change(root, "highways/data.geojson", (source) => source.replace("75,", "275,"));
    await expect(loadPublicData(root, true)).rejects.toThrow(/geometry.coordinates/);
  });
  it("refuses a public directory symlink pointing outside the approved root", async () => {
    const root = await copy();
    await rm(resolve(root, "public_chargers"), { recursive: true });
    await symlink(
      resolve(fixtureRoot, "public_chargers"),
      resolve(root, "public_chargers"),
      process.platform === "win32" ? "junction" : "dir",
    );
    await expect(loadPublicData(root, true)).rejects.toThrow(
      /must stay inside the public data root/,
    );
  });
  it("emits only validated public assets and preserves source licensing", async () => {
    const { catalogue, artifacts } = await loadPublicData(publicRoot);
    expect(catalogue.districts).toHaveLength(783);
    expect(catalogue.pending).toContain("ev_registrations");
    expect(artifacts.some(({ name }) => /fixtures|owner|station_inventory/.test(name))).toBe(false);
    expect(artifacts.some(({ source }) => /Test Station 01|test-public-charger/.test(source))).toBe(
      false,
    );
    expect(artifacts.find(({ name }) => name.endsWith("README.txt"))?.source).toContain("CC0-1.0");
  });
  it("the build's CLI exits nonzero and names the broken public CSV cell", async () => {
    const root = await copy(publicRoot);
    await change(root, "district_reference/data.csv", (source) =>
      source.replace(/(\r?\n)\d+,/, "$1-1,"),
    );
    const result = spawnSync(
      process.execPath,
      [fileURLToPath(new URL("./validate-public-data.ts", import.meta.url)), "--root", root],
      { encoding: "utf8" },
    );
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/district_reference[/\\]data.csv: row 2, column lgd_code:/);
  });
});
