import { it, expect } from "vitest";
import { loadPublicData } from "./public-data";
import { datasetStructuredData, sitemap } from "./analytics-seo";

it("describes every downloadable dataset using its actual licence, source and URL", async () => {
  const { catalogue } = await loadPublicData("../data/public");
  const graph = datasetStructuredData(catalogue)["@graph"];
  expect(graph).toHaveLength(catalogue.datasets.length);
  graph.forEach((row, i) => {
    expect(row.license).toBe(
      catalogue.datasets[i]!.metadata.licence_url ?? catalogue.datasets[i]!.metadata.licence,
    );
    expect(row.distribution.contentUrl).toBe(catalogue.datasets[i]!.data_url);
    expect(row.isBasedOn.url).toBe(catalogue.datasets[i]!.metadata.source_url);
  });
});

it("emits only the supplied publication list and refuses an unverified origin shape", () => {
  const xml = sitemap("https://example.org", ["/data", "/data/sources"]);
  expect(xml).toContain("https://example.org/data/sources");
  expect(xml).not.toContain("/data/district");
  for (const origin of [
    "http://example.org",
    "https://example.org/private",
    "https://u:p@example.org",
  ])
    expect(() => sitemap(origin, [])).toThrow("HTTPS origin");
});
