import type { PublicCatalogue } from "../src/features/analytics/data/schemas.ts";

export function datasetStructuredData(catalogue: PublicCatalogue) {
  return {
    "@context": "https://schema.org",
    "@graph": catalogue.datasets.map(({ id, metadata: meta, data_url }) => ({
      "@type": "Dataset",
      "@id": `/data/sources#source-${id}`,
      name: meta.title,
      description: meta.description,
      license: meta.licence_url ?? meta.licence,
      isBasedOn: { "@type": "CreativeWork", name: meta.source_name, url: meta.source_url },
      dateModified: meta.retrieved_on,
      temporalCoverage: meta.time_coverage,
      distribution: {
        "@type": "DataDownload",
        contentUrl: data_url,
        encodingFormat: data_url.endsWith(".csv") ? "text/csv" : "application/json",
      },
    })),
  };
}

export function sitemap(origin: string, paths: readonly string[]) {
  const url = new URL(origin);
  if (
    url.protocol !== "https:" ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== "/"
  )
    throw new Error("PUBLIC_ANALYTICS_ORIGIN must be an HTTPS origin");
  const escape = (value: string) =>
    value
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  return (
    '<?xml version="1.0" encoding="UTF-8"?>\n' +
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    paths.map((path) => `<url><loc>${escape(new URL(path, url).href)}</loc></url>`).join("\n") +
    "\n</urlset>\n"
  );
}
