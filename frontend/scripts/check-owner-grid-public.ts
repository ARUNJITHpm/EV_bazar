import { readFile, readdir } from "node:fs/promises";
import { resolve, relative } from "node:path";

const root = resolve(process.argv[2] ?? "dist");
const privateFields =
  /owner_grid_revisions|owner_grid_consents|owner_outage_revisions|sanctioned_load_kva|connected_load_kw|transformer_rating_kva|approximate_hours/;
let checked = 0;
async function walk(directory: string): Promise<void> {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) {
      await walk(path);
      continue;
    }
    if (!/\.(html|json|csv|js|map|txt)$/.test(entry.name)) continue;
    const body = await readFile(path, "utf8");
    const name = relative(root, path).replaceAll("\\", "/");
    if (body.includes("PrivateOwnerGridCanary")) throw new Error(`Private grid canary in ${name}`);
    // The shared SPA necessarily contains owner form/schema code. Inspect only
    // public data payloads and pre-rendered /data HTML for private field names.
    if (
      (name.startsWith("data/") ||
        name.startsWith("analytics-data/") ||
        /\.(json|csv)$/.test(name)) &&
      privateFields.test(body)
    ) {
      throw new Error(`Private owner grid field in public artifact ${name}`);
    }
    checked++;
  }
}
await walk(root);
console.log(
  `PASS: ${checked} built artifacts contain no private grid canary; public payloads contain no grid fields.`,
);
