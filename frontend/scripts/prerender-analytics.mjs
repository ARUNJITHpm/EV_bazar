import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import react from "@vitejs/plugin-react";
import { build } from "vite";
import { publicDataPlugin } from "./public-data-plugin.ts";

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
