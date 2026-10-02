// Build-only: HF's orphan git mirror rejects binary blobs. Browser font bytes
// remain identical; their text representation never enters a runtime bundle.
import { createHash } from "node:crypto";
import { readFile, writeFile, mkdir } from "node:fs/promises";

const fonts = JSON.parse(await readFile(new URL("../font-assets.json", import.meta.url), "utf8"));
const names = ["IBMPlexMono.woff2", "SourceSerif4.woff2"];
if (Object.keys(fonts).sort().join() !== names.join()) throw new Error("Unexpected font asset set");
const directory = new URL("../public/analytics-fonts/", import.meta.url);
await mkdir(directory, { recursive: true });
for (const name of names) {
  const { base64, sha256 } = fonts[name];
  const bytes = Buffer.from(base64, "base64");
  if (
    bytes.subarray(0, 4).toString() !== "wOF2" ||
    createHash("sha256").update(bytes).digest("hex") !== sha256
  )
    throw new Error(`Font integrity check failed: ${name}`);
  await writeFile(new URL(name, directory), bytes);
}
console.log("Materialized two hash-verified, fully licensed WOFF2 fonts.");
