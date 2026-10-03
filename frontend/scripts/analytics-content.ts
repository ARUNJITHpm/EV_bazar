import { readFile, readdir, realpath } from "node:fs/promises";
import { resolve, relative, isAbsolute } from "node:path";
import { z } from "zod";
import type { PublicCatalogue } from "../src/features/analytics/data/schemas";
import type { Article, ContentBlock } from "../src/features/analytics/content/model";
import type { ChartData } from "../src/features/analytics/chart/model";
const date = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/)
  .refine((v) => {
    const d = new Date(`${v}T00:00:00Z`);
    return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === v;
  }, "Invalid calendar date");
const text = z.string().trim().min(1);
const vertical = z.enum([
  "vehicles",
  "charging-network",
  "electricity",
  "usage",
  "corridors",
  "method",
]);
const chartSchema = z
  .object({ dataset: z.literal("district_reference"), kind: z.enum(["total", "by-state"]) })
  .strict();
const insightSchema = z
  .object({
    title: text,
    question: text,
    summary: text,
    vertical,
    authors: z.array(text).min(1),
    published_on: date,
    updated_on: date,
    datasets: z.array(z.literal("district_reference")).min(1),
    changelog: z.array(z.object({ date, entry: text }).strict()).min(1),
  })
  .strict();
const weeklySchema = z
  .object({
    title: text.refine((v) => v.endsWith("?"), "Weekly title must be a question"),
    published_on: date,
    vertical,
    dataset: z.literal("district_reference"),
    chart: chartSchema,
    social_caption: text.max(299),
  })
  .strict();
function referenceChart(
  config: z.infer<typeof chartSchema>,
  catalogue: PublicCatalogue,
  id: string,
): ChartData {
  const source = catalogue.datasets.find((d) => d.id === config.dataset);
  if (!source || source.metadata.fixture || !catalogue.districts.length)
    throw new Error("Content requires a verified public dataset");
  const counts = new Map<string, number>();
  for (const d of catalogue.districts)
    counts.set(d.state_name, (counts.get(d.state_name) ?? 0) + 1);
  const categories =
    config.kind === "total"
      ? [["Archived district entries", catalogue.districts.length] as const]
      : [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  const data: ChartData = {
    social: {
      question:
        config.kind === "total"
          ? "How many entries are in the archived district reference?"
          : "How do archived district entries vary by state?",
      context: source.metadata.time_coverage.match(/\b20\d{2}\b/)
        ? `Archived reference \u00b7 ${source.metadata.time_coverage.match(/\b20\d{2}\b/)![0]} coverage`
        : "Archived reference; see source period",
    },
    id,
    title:
      config.kind === "total"
        ? "Entries in the archived district reference"
        : "Archived district entries by state or union territory",
    subtitle: source.metadata.time_coverage,
    summary:
      "Counts of reference entries, not a current administrative census or a measure of EV charging.",
    type: config.kind === "total" ? "bar" : "horizontal-bar",
    unit: "district reference entries",
    rows: categories.map(([label, value]) => ({
      region: config.kind === "total" ? "India" : label,
      period: source.metadata.time_coverage,
      indicator: "Reference entries",
      series: "Archived reference",
      label,
      value,
      status: "observed",
    })),
    sources: [
      {
        name: source.metadata.source_name,
        url: source.metadata.source_url,
        licence: source.metadata.licence,
        licence_url: source.metadata.licence_url,
        attribution: source.metadata.attribution,
      },
    ],
    updated: source.metadata.retrieved_on,
    notes: [
      source.metadata.notes,
      "Local Government Directory (LGD) codes identify the entries. Names and boundaries may have changed since this archive.",
    ],
    versions: { ...catalogue.versions, renderer_version: "analytics_content_chart_v2" },
  };
  return data;
}
export function parseArticle(
  source: string,
  slug: string,
  format: Article["format"],
  catalogue: PublicCatalogue,
): Article {
  if (!/^[a-z][a-z0-9-]*$/.test(slug)) throw new Error("Invalid article slug");
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/.exec(source);
  if (!match) throw new Error("Content needs JSON front matter between --- delimiters");
  const raw: unknown = JSON.parse(match[1]!);
  const meta = format === "insights" ? insightSchema.parse(raw) : weeklySchema.parse(raw);
  const body = match[2]!.trim();
  const blocks: ContentBlock[] = [];
  let chartCount = 0;
  for (const block of body.split(/\r?\n\s*\r?\n/)) {
    if (block.startsWith(":::chart ")) {
      const config = chartSchema.parse(JSON.parse(block.slice(9)));
      if (format === "weekly") throw new Error("Weekly chart belongs in front matter only");
      blocks.push({
        kind: "chart",
        data: referenceChart(config, catalogue, `${slug}-${++chartCount}`),
      });
    } else if (block.startsWith("## ") && !block.includes("\n"))
      blocks.push({ kind: "heading", text: block.slice(3) });
    else if (block.split(/\r?\n/).every((line) => line.startsWith("- ")))
      blocks.push({ kind: "list", items: block.split(/\r?\n/).map((line) => line.slice(2)) });
    else {
      if (/^(#|:::|```|>|<)/m.test(block) || /<[^>]*>/.test(block))
        throw new Error("Unsupported Markdown; HTML and executable content are forbidden");
      blocks.push({ kind: "paragraph", text: block.replace(/\s*\r?\n\s*/g, " ") });
    }
  }
  for (const block of blocks) {
    const values =
      block.kind === "paragraph" || block.kind === "heading"
        ? [block.text]
        : block.kind === "list"
          ? block.items
          : [];
    for (const value of values)
      for (const link of value.matchAll(/\[[^\]]+\]\(([^)]+)\)/g))
        if (!/^https:\/\/|^\/data(?:\/|$)/.test(link[1]!))
          throw new Error("Markdown links must use HTTPS or /data routes");
  }
  if ("chart" in meta) {
    if (body.split(/\s+/).filter(Boolean).length > 150)
      throw new Error("Weekly explanation exceeds 150 words");
    if (meta.chart.dataset !== meta.dataset) throw new Error("Weekly dataset and chart disagree");
    blocks.unshift({ kind: "chart", data: referenceChart(meta.chart, catalogue, `${slug}-chart`) });
    const weeklyChart = blocks[0];
    if (weeklyChart?.kind === "chart" && weeklyChart.data.social)
      weeklyChart.data.social.question = meta.title;
    return {
      slug,
      format,
      title: meta.title,
      question: meta.title,
      summary: body,
      vertical: meta.vertical,
      authors: ["Chargeworthy Data"],
      published_on: meta.published_on,
      updated_on: meta.published_on,
      datasets: [meta.dataset],
      changelog: [],
      social_caption: meta.social_caption,
      blocks,
    };
  }
  if (
    meta.updated_on < meta.published_on ||
    meta.changelog.some((c) => c.date < meta.published_on || c.date > meta.updated_on)
  )
    throw new Error("Article dates and changelog disagree");
  if (!meta.changelog.some((c) => c.date === meta.updated_on))
    throw new Error("Latest update needs a changelog entry");
  if (chartCount < 2) throw new Error("Insights require several sourced charts");
  return { ...meta, slug, format, blocks };
}
export async function loadAnalyticsContent(
  root: string,
  catalogue: PublicCatalogue,
): Promise<Article[]> {
  const articles: Article[] = [];
  const canonical = await realpath(root);
  for (const format of ["insights", "weekly"] as const) {
    for (const file of (await readdir(resolve(root, format))).sort()) {
      if (!file.endsWith(".md"))
        throw new Error("Only reviewed Markdown belongs in the content tree");
      const target = await realpath(resolve(root, format, file));
      const within = relative(canonical, target);
      if (within.startsWith("..") || isAbsolute(within))
        throw new Error("Content must stay inside its public root");
      try {
        articles.push(
          parseArticle(await readFile(target, "utf8"), file.slice(0, -3), format, catalogue),
        );
      } catch (error) {
        throw new Error(
          `${format}/${file}: ${error instanceof Error ? error.message : "Invalid article"}`,
        );
      }
    }
  }
  return articles;
}
