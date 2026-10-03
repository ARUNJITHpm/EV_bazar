import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import react from "@vitejs/plugin-react";
import { build, loadEnv } from "vite";
import { Resvg } from "@resvg/resvg-js";
import { createHash } from "node:crypto";
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
const {
  renderAnalytics,
  staticAnalyticsPaths,
  analyticsMetadata,
  socialArticles,
  socialSvg,
  socialFormats,
  socialImagePath,
  assertSocialSvgLegibility,
  pngWithProvenance,
} = await import(pathToFileURL(resolve(output, "render.mjs")).href);
// Node and rasterisation are build-only; Caddy serves the resulting static PNGs.
const configuredOrigin = process.env.VITE_ANALYTICS_SITE_ORIGIN ?? "";
const origin = configuredOrigin || "http://localhost:4173";
const parsedOrigin = new URL(origin);
if (
  parsedOrigin.origin !== origin ||
  (configuredOrigin &&
    (parsedOrigin.protocol !== "https:" || parsedOrigin.hostname === "localhost"))
)
  throw new Error(
    "VITE_ANALYTICS_SITE_ORIGIN must be a public HTTPS origin with no path or trailing slash",
  );
if (!configuredOrigin)
  console.warn(
    "Social images are local previews. Set VITE_ANALYTICS_SITE_ORIGIN before deploying link previews.",
  );
const tokenCss = await readFile("src/styles/tokens.css", "utf8");
const tokenNames = {
  paper: "--cw-paper",
  ink: "--cw-ink",
  muted: "--cw-paper-muted",
  slate: "--cw-paper-slate",
  rule: "--cw-rule",
  highlight: "--cw-data-highlight",
};
const palette = Object.fromEntries(
  Object.entries(tokenNames).map(([key, token]) => {
    const value = new RegExp(`${token}:\\s*(#[0-9a-f]{6})`, "i").exec(tokenCss)?.[1];
    if (!value) throw new Error(`Missing report palette token ${token}`);
    return [key, value];
  }),
);
const fontDirectory = resolve("public/analytics-fonts");
const fontManifest = JSON.parse(await readFile(resolve(fontDirectory, "provenance.json"), "utf8"));
for (const [name, entry] of Object.entries(fontManifest.files)) {
  if (
    createHash("sha256")
      .update(await readFile(resolve(fontDirectory, name)))
      .digest("hex") !== entry.sha256
  )
    throw new Error(`Font provenance mismatch: ${name}`);
}
const fontFiles = ["SourceSerif4.ttf", "IBMPlexMono.ttf"].map((name) =>
  resolve(fontDirectory, name),
);
await mkdir("dist/analytics-images", { recursive: true });
const imageManifest = { public_origin_confirmed: Boolean(configuredOrigin), origin, images: [] };
for (const article of socialArticles.filter((a) => a.format === "weekly")) {
  const chart = article.blocks.find((b) => b.kind === "chart");
  if (!chart) throw new Error(`Weekly post has no chart: ${article.slug}`);
  for (const [format, dimensions] of Object.entries(socialFormats)) {
    const svg = socialSvg({
      data: chart.data,
      rows: chart.data.rows,
      question: article.question,
      pageUrl: `${origin}/data/weekly/${article.slug}`,
      format,
      palette,
    });
    assertSocialSvgLegibility(svg, format);
    const renderer = new Resvg(svg, {
      font: { fontFiles, loadSystemFonts: false },
      fitTo: { mode: "original" },
    });
    const png = pngWithProvenance(renderer.render().asPng(), svg);
    const path = socialImagePath(article.slug, format);
    await writeFile(`dist${path}`, png);
    // SVG is a public audit artifact for font/bounds checks; all values came
    // through the same reviewed public content loader as the article.
    await writeFile(`dist${path.replace(/\.png$/, ".svg")}`, svg);
    imageManifest.images.push({
      article: article.slug,
      format,
      path,
      width: dimensions.width,
      height: dimensions.height,
      sha256: createHash("sha256").update(png).digest("hex"),
    });
  }
}
await writeFile("dist/analytics-images/manifest.json", JSON.stringify(imageManifest, null, 2));
console.log(`Generated ${imageManifest.images.length} reviewed weekly social PNGs.`);
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
  const weekly = socialArticles.find(
    (a) => a.format === "weekly" && path === `/data/weekly/${a.slug}`,
  );
  if (weekly) {
    const image = `${configuredOrigin}${socialImagePath(weekly.slug, "og")}`;
    html = html
      .replace(/<meta\s+property="og:image"[^>]*>/g, "")
      .replace(
        "</head>",
        `<meta property="og:image" content="${escape(image)}" /><meta property="og:image:width" content="1200" /><meta property="og:image:height" content="630" /><meta property="og:image:alt" content="${escape(weekly.question)}" /></head>`,
      );
  }
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
