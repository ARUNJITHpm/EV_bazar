import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import react from "@vitejs/plugin-react";
import { build, loadEnv } from "vite";
import { publicDataPlugin } from "./public-data-plugin.ts";
import { sitemap, datasetStructuredData } from "./analytics-seo.ts";

// Build-time only. Render just the public analytics tree: no API, owner,
// console, fixture or report imports are reachable from this entry point.
const output = resolve("node_modules/.cache/analytics-prerender");
await build({
  configFile: false,
  plugins: [react(), publicDataPlugin()],
  build: {
    ssr: "src/features/analytics/prerender.tsx",
    outDir: output,
    emptyOutDir: true,
    rollupOptions: { output: { entryFileNames: "render.mjs" } },
  },
});
const { renderAnalytics, staticAnalyticsPaths, analyticsMetadata } = await import(
  pathToFileURL(resolve(output, "render.mjs")).href
);
const template = await readFile("dist/index.html", "utf8");
const catalogue = JSON.parse(await readFile("dist/analytics-data/catalogue.json", "utf8"));
const analyticsOrigin =
  process.env.PUBLIC_ANALYTICS_ORIGIN ??
  loadEnv("production", process.cwd(), "PUBLIC_").PUBLIC_ANALYTICS_ORIGIN;
const published = staticAnalyticsPaths.filter((path) => !analyticsMetadata(path).noindex);
await writeFile("dist/analytics-data/published-routes.json", JSON.stringify(published, null, 2));
if (analyticsOrigin) await writeFile("dist/sitemap.xml", sitemap(analyticsOrigin, published));
else
  console.warn(
    "Sitemap/canonical URLs pending: set PUBLIC_ANALYTICS_ORIGIN to the verified HTTPS origin.",
  );
const escape = (value) =>
  value
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
function documentFor(path) {
  const metadata = analyticsMetadata(path);
  let html = template.replace(
    /<title>[\s\S]*?<\/title>/,
    `<title>${escape(metadata.title)}</title>`,
  );
  // Analytics uses self-hosted fonts with swap. A remote stylesheet must not
  // hold up the otherwise readable prerendered document on mobile networks.
  html = html.replace(/<link\s[^>]*href="https:\/\/fonts\.(?:googleapis|gstatic)\.com[^>]*>/g, "");
  // Paint the public reading surface before starting SPA enhancement. Other
  // routes retain their ordinary bootstrap; static links work immediately.
  html = html.replace(
    /<script type="module" crossorigin src="(\/assets\/[^"<>]+\.js)"><\/script>/,
    (_tag, src) =>
      `<script type="module">requestAnimationFrame(() => requestAnimationFrame(() => import(${JSON.stringify(src)})));</script>`,
  );
  if (analyticsOrigin)
    html = html.replace(
      "</head>",
      `<link rel="canonical" href="${escape(new URL(path, analyticsOrigin).href)}" /></head>`,
    );
  if (path === "/data/sources")
    html = html.replace(
      "</head>",
      `<script id="analytics-datasets" type="application/ld+json">${JSON.stringify(datasetStructuredData(catalogue)).replaceAll("<", "\\u003c")}</script></head>`,
    );
  html = html.replace(
    /(<meta\s+name="description"\s+content=")[^"]*(")/,
    `$1${escape(metadata.description)}$2`,
  );
  html = html.replace(
    /(<meta\s+property="og:title"\s+content=")[^"]*(")/,
    `$1${escape(metadata.title)}$2`,
  );
  html = html.replace(
    /(<meta\s+property="og:description"\s+content=")[^"]*(")/,
    `$1${escape(metadata.description)}$2`,
  );
  html = html.replace(
    "</head>",
    `<meta name="robots" content="${metadata.noindex ? "noindex, follow" : "index, follow"}" /></head>`,
  );
  const marker = '<div id="root"></div>';
  if (!html.includes(marker))
    throw new Error("Analytics prerender: missing root marker in dist/index.html");
  return html.replace(
    marker,
    () => `<div id="root" data-analytics-path="${escape(path)}">${renderAnalytics(path)}</div>`,
  );
}
for (const path of staticAnalyticsPaths) {
  if (!/^\/data(?:\/[a-z0-9-]+)*$/.test(path)) throw new Error(`Unsafe analytics route: ${path}`);
  const destination = resolve(`dist${path}`);
  await mkdir(destination, { recursive: true });
  await writeFile(resolve(destination, "index.html"), documentFor(path), "utf8");
}
await writeFile("dist/data/fallback.html", documentFor("/data/unpublished"), "utf8");
console.log(
  `Prerendered ${staticAnalyticsPaths.length} public analytics documents and an unpublished-page fallback.`,
);
