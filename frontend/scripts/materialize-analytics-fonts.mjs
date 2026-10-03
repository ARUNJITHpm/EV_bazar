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

// The social-image prerender needs TTFs, which stay out of git for the same
// reason. A clean checkout (the Space's Docker build) fetches each one from
// the pinned google/fonts revision in provenance.json and refuses any byte
// that does not match its recorded hash.
const provenance = JSON.parse(await readFile(new URL("provenance.json", directory), "utf8"));
let fetched = 0;
for (const [name, { path, sha256 }] of Object.entries(provenance.files)) {
  const target = new URL(name, directory);
  const present = await readFile(target).catch(() => null);
  if (present && createHash("sha256").update(present).digest("hex") === sha256) continue;
  const url = `https://raw.githubusercontent.com/google/fonts/${provenance.revision}/${path}`;
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Font download failed (${response.status}): ${url}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (createHash("sha256").update(bytes).digest("hex") !== sha256)
    throw new Error(`Font integrity check failed: ${name}`);
  await writeFile(target, bytes);
  fetched += 1;
}
if (fetched) console.log(`Fetched ${fetched} hash-verified font file(s) from the pinned revision.`);
