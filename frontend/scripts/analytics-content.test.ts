// @vitest-environment node
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { loadPublicData } from "./public-data";
import { loadAnalyticsContent, parseArticle } from "./analytics-content";
import { validateChart } from "../src/features/analytics/chart/model";
const root = fileURLToPath(new URL("../content/analytics", import.meta.url));
const publicRoot = fileURLToPath(new URL("../../data/public", import.meta.url));
const catalogue = (await loadPublicData(publicRoot)).catalogue;
const weekly = await readFile(
  `${root}/weekly/how-many-entries-in-the-district-reference.md`,
  "utf8",
);
const insight = await readFile(
  `${root}/insights/what-does-the-district-reference-cover.md`,
  "utf8",
);
function mutate(source: string, fn: (meta: Record<string, unknown>) => void, body?: string) {
  const pieces = source.split("---");
  const meta = JSON.parse(pieces[1]!) as Record<string, unknown>;
  fn(meta);
  return `---\n${JSON.stringify(meta)}\n---\n${body ?? pieces[2]!.trim()}`;
}
describe("reviewed public content", () => {
  it("loads live sourced charts with derived counts, sources and all stamps", async () => {
    const articles = await loadAnalyticsContent(root, catalogue);
    expect(articles).toHaveLength(2);
    for (const article of articles)
      for (const block of article.blocks)
        if (block.kind === "chart") {
          validateChart(block.data);
          expect(block.data.rows.reduce((n, r) => n + (r.value ?? 0), 0)).toBe(
            catalogue.districts.length,
          );
          expect(block.data.sources[0]?.url).toBe(catalogue.datasets[0]?.metadata.source_url);
        }
  });
  it("refuses unavailable and fixture datasets", () => {
    expect(() => parseArticle(weekly, "weekly", "weekly", { ...catalogue, datasets: [] })).toThrow(
      /verified public/,
    );
    expect(() =>
      parseArticle(weekly, "weekly", "weekly", {
        ...catalogue,
        datasets: catalogue.datasets.map((d) => ({
          ...d,
          metadata: { ...d.metadata, fixture: true },
        })),
      }),
    ).toThrow(/verified public/);
  });
  it.each([
    ["length", mutate(weekly, () => {}, "word ".repeat(151))],
    [
      "caption",
      mutate(weekly, (m) => {
        m.social_caption = "a".repeat(300);
      }),
    ],
    [
      "question",
      mutate(weekly, (m) => {
        m.title = "No question";
      }),
    ],
    [
      "date",
      mutate(weekly, (m) => {
        m.published_on = "2026-02-30";
      }),
    ],
    [
      "dataset",
      mutate(weekly, (m) => {
        m.dataset = "owner_bills";
      }),
    ],
    [
      "second chart",
      mutate(weekly, () => {}, ':::chart {"dataset":"district_reference","kind":"total"}'),
    ],
    ["HTML", mutate(weekly, () => {}, "<script>alert(1)</script>")],
    ["unsafe link", mutate(weekly, () => {}, "[Open](javascript:alert)")],
    [
      "private field",
      mutate(weekly, (m) => {
        m.owner_phone = "forbidden";
      }),
    ],
  ])("rejects invalid weekly %s", (_label, source) => {
    expect(() => parseArticle(source, "weekly", "weekly", catalogue)).toThrow();
  });
  it("requires consistent updates, changelog and several charts", () => {
    expect(() =>
      parseArticle(
        mutate(insight, (m) => {
          m.updated_on = "2026-09-30";
        }),
        "insight",
        "insights",
        catalogue,
      ),
    ).toThrow(/dates/);
    expect(() =>
      parseArticle(
        mutate(insight, (m) => {
          m.changelog = [];
        }),
        "insight",
        "insights",
        catalogue,
      ),
    ).toThrow();
    expect(() =>
      parseArticle(
        mutate(insight, () => {}, ':::chart {"dataset":"district_reference","kind":"total"}'),
        "insight",
        "insights",
        catalogue,
      ),
    ).toThrow(/several/);
  });
});
