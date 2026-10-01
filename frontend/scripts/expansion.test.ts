// @vitest-environment node
import { cp, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { afterEach, expect, it } from "vitest";
import { buildExpansion } from "./expansion";
import { loadPublicData } from "./public-data";
import { parseCsv } from "./csv";
const temporary: string[] = [];
afterEach(async () => {
  for (const p of temporary.splice(0)) await rm(p, { recursive: true, force: true });
});
it("production consumers use validated artifacts and keep pending sources empty", async () => {
  const loaded = await loadPublicData(resolve("../data/public"));
  const data = buildExpansion(loaded, "2026-10-02");
  expect(data).toEqual({
    asOf: "2026-10-02",
    performance: [],
    supply: [],
    policies: [],
    amenities: [],
  });
});
it("validates an explicitly scoped national PFC reference without relaxing state joins", async () => {
  const root = await mkdtemp(resolve(tmpdir(), "part15-national-"));
  temporary.push(root);
  await cp(resolve("../data/fixtures"), root, { recursive: true });
  const file = resolve(root, "discom_performance/data.csv");
  const records = parseCsv(await readFile(file, "utf8"), file);
  const row = [...records[1]!.values],
    header = records[0]!.values;
  row[header.indexOf("state")] = "India";
  row[header.indexOf("discom_id")] = "national";
  row[header.indexOf("discom")] = "India national reference";
  const cell = (s: string) => `"${s.replaceAll('"', '""')}"`;
  await writeFile(
    file,
    [...records.map((r) => r.values), row].map((r) => r.map(cell).join(",")).join("\n") + "\n",
  );
  expect(
    buildExpansion(await loadPublicData(root, true), "2026-10-02").performance.some(
      (r) => r.state === "India",
    ),
  ).toBe(true);
  row[header.indexOf("discom_id")] = "unreviewed-utility";
  await writeFile(file, [header, row].map((r) => r.map(cell).join(",")).join("\n") + "\n");
  await expect(loadPublicData(root, true)).rejects.toThrow(/state is absent/);
  row[header.indexOf("state")] = records[1]!.values[header.indexOf("state")]!;
  row[header.indexOf("discom_id")] = "national";
  await writeFile(file, [header, row].map((r) => r.map(cell).join(",")).join("\n") + "\n");
  await expect(loadPublicData(root, true)).rejects.toThrow(/national reference/);
});
