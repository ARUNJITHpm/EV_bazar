import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPublicData } from "./public-data.ts";

const override = process.argv.indexOf("--root");
const root =
  override < 0
    ? fileURLToPath(new URL("../../data/public", import.meta.url))
    : resolve(process.argv[override + 1] ?? "");
try {
  const { catalogue } = await loadPublicData(root);
  console.log(
    `Public data valid: ${catalogue.datasets.length} sourced datasets, ${catalogue.districts.length} district references; pending: ${catalogue.pending.join(", ") || "none"}.`,
  );
} catch (error) {
  console.error(error instanceof Error ? error.message : "Public data validation failed");
  process.exitCode = 1;
}
