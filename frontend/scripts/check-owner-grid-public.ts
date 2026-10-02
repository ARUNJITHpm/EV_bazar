import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { scanPrivateBuild } from "./private-build.ts";

const root = resolve(process.argv[2] ?? "dist");
const snapshot = process.argv[3];
const records: unknown = snapshot
  ? JSON.parse(await readFile(resolve(snapshot), "utf8"))
  : undefined;
const result = await scanPrivateBuild(root, records);
console.log(
  `PASS: ${result.artifacts} artifacts scanned; public payloads contain no private owner/grid fields; ${result.private_record_values} private snapshot values checked.`,
);
if (!result.live_records_checked)
  console.log(
    "Live private-record comparison not run: supply a local JSON snapshot as the second argument.",
  );
