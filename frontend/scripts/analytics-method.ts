import { readFile, realpath } from "node:fs/promises";
import { isAbsolute, relative, resolve } from "node:path";
import {
  validationSummarySchema,
  correctionsSchema,
  type ReviewedMethod,
} from "../src/features/analytics/method/reviewed.ts";
import type { Article } from "../src/features/analytics/content/model.ts";
// Only two explicitly reviewed public files are read. Never load private reports.
export async function loadAnalyticsMethod(
  root: string,
  articles: readonly Article[],
): Promise<ReviewedMethod> {
  const canonical = await realpath(root);
  async function optional(name: string): Promise<unknown | undefined> {
    let path: string;
    try {
      path = await realpath(resolve(root, name));
    } catch (error) {
      if ((error as NodeJS.ErrnoException).code === "ENOENT") return undefined;
      throw error;
    }
    const within = relative(canonical, path);
    if (within.startsWith("..") || isAbsolute(within))
      throw new Error(`${name}: file must stay inside reviewed content root`);
    try {
      return JSON.parse(await readFile(path, "utf8")) as unknown;
    } catch {
      throw new Error(`${name}: invalid JSON`);
    }
  }
  const raw = await optional("validation-summary.json");
  const validation = raw === undefined ? null : validationSummarySchema.parse(raw);
  const rawCorrections = await optional("corrections.json");
  const corrections = correctionsSchema.parse(rawCorrections === undefined ? [] : rawCorrections);
  const known = new Set(
    articles.flatMap((a) => a.blocks.flatMap((b) => (b.kind === "chart" ? [b.data.id] : []))),
  );
  const ids = new Set<string>();
  for (const correction of corrections) {
    if (ids.has(correction.id))
      throw new Error(`corrections.json: duplicate correction ${correction.id}`);
    ids.add(correction.id);
    for (const chart of correction.charts)
      if (!known.has(chart)) throw new Error(`corrections.json: unknown chart ${chart}`);
  }
  return {
    validation,
    corrections: corrections.sort(
      (a, b) => b.date.localeCompare(a.date) || a.id.localeCompare(b.id),
    ),
  };
}
