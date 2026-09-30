import { readFile, writeFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";
import { spawnSync } from "node:child_process";

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
  const npmCli = process.env.npm_execpath;
  if (!npmCli) throw new Error("Run this check with npm run data:check-build");
  const result = spawnSync(process.execPath, [npmCli, "run", "build"], { encoding: "utf8" });
  const output = `${result.stdout}${result.stderr}`;
  if (result.status === 0 || !/data.csv: row 2, column lgd_code:/.test(output))
    throw new Error(`Broken CSV did not produce the expected build refusal:\n${output}`);
  console.log("PASS: npm run build refused district_reference/data.csv, row 2, column lgd_code.");
} finally {
  await writeFile(reference, original);
}

async function scan(directory: string): Promise<void> {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) await scan(path);
    else if (/\.(?:html|json|js|map|csv|txt)$/.test(entry.name)) {
      const source = await readFile(path, "utf8");
      if (
        /Test Station 01|Test District 01|test-public-charger-01|test-district-999001|example\.invalid\/test-source/.test(
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
