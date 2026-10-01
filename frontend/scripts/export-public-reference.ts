import { createHash } from "node:crypto";
import { mkdir, rename, writeFile, realpath, rm } from "node:fs/promises";
import { dirname, resolve, relative, isAbsolute, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPublicData } from "./public-data.ts";

// Offline/build operation only. Deploy this exact snapshot and the source tree
// together; pin the printed digest in the backend release configuration.
export async function exportPublicReference(root: string, output: string) {
  const loaded = await loadPublicData(root);
  const bytes = JSON.stringify(loaded.reference) + "\n";
  const sha256 = createHash("sha256").update(bytes).digest("hex");
  const within = relative(await realpath(root), resolve(output));
  if (within !== ".." && !within.startsWith(`..${sep}`) && !isAbsolute(within))
    throw new Error("Snapshot output must stay outside the public source root");
  await mkdir(dirname(output), { recursive: true });
  const resolvedParent = await realpath(dirname(output));
  const resolvedWithin = relative(await realpath(root), resolvedParent);
  if (
    resolvedWithin !== ".." &&
    !resolvedWithin.startsWith(`..${sep}`) &&
    !isAbsolute(resolvedWithin)
  )
    throw new Error("Snapshot output directory points into the public source root");
  const temporary = `${output}.${process.pid}.tmp`;
  let created = false;
  try {
    await writeFile(temporary, bytes, { flag: "wx" });
    created = true;
    await rename(temporary, output);
  } finally {
    if (created) await rm(temporary, { force: true });
  }
  return sha256;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [root, output] = process.argv.slice(2);
  if (!root || !output)
    throw new Error("Usage: node export-public-reference.ts <public-root> <output.json>");
  console.log(
    `Validated reference SHA256: ${await exportPublicReference(resolve(root), resolve(output))}`,
  );
}
