import { readFile, readdir } from "node:fs/promises";
import { relative, resolve } from "node:path";

const privateFields =
  /\b(?:owner_id|owner_account_id|station_id|owner_stations|owner_accounts|owner_bills|owner_readings|owner_bill_images|owner_grid_revisions|owner_grid_consents|owner_outage_revisions|sanctioned_load_kva|connected_load_kw|transformer_rating_kva|approximate_hours|phone|email|bill_image_key)\b/;

export async function scanPrivateBuild(root: string, privateRecords?: unknown) {
  const strings = new Set(["PrivateOwnerGridCanary", "PrivateOwnerLaunchCanary"]);
  function collect(value: unknown) {
    if (typeof value === "string" && value.length >= 8) strings.add(value);
    else if (Array.isArray(value)) value.forEach(collect);
    else if (value && typeof value === "object") Object.values(value).forEach(collect);
  }
  if (privateRecords !== undefined) {
    if (!privateRecords || typeof privateRecords !== "object")
      throw new Error("Private records must be a local JSON object or array");
    collect(privateRecords);
  }
  let checked = 0;
  async function walk(directory: string): Promise<void> {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      const path = resolve(directory, entry.name);
      if (entry.isSymbolicLink()) throw new Error("Build scan refuses symbolic links");
      if (entry.isDirectory()) {
        await walk(path);
        continue;
      }
      const bytes = await readFile(path);
      const name = relative(root, path).replaceAll("\\", "/");
      for (const value of strings) {
        // Never print private contents, even when refusing a leak.
        if (
          bytes.includes(Buffer.from(value)) ||
          bytes.includes(Buffer.from(JSON.stringify(value).slice(1, -1)))
        )
          throw new Error(
            value === "PrivateOwnerGridCanary"
              ? `Private grid canary in ${name}`
              : `Private record value in built artifact ${name}`,
          );
      }
      // Owner form names necessarily exist in the single SPA and its source
      // maps. Values above are checked everywhere; fields only in public data.
      if (
        (name.startsWith("data/") ||
          name.startsWith("analytics-data/") ||
          /\.(json|csv)$/.test(name)) &&
        privateFields.test(bytes.toString("utf8"))
      )
        throw new Error(
          `Private owner field (Private owner grid field) in public artifact ${name}`,
        );
      checked++;
    }
  }
  await walk(root);
  return {
    artifacts: checked,
    private_record_values: strings.size - 2,
    live_records_checked: privateRecords !== undefined,
  };
}
