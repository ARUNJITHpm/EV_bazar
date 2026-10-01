import { loadAnalyticsMethod } from "./analytics-method.ts";
import { loadAnalyticsContent } from "./analytics-content.ts";
import { resolve } from "node:path";
import type { Plugin } from "vite";
import { loadPublicData } from "./public-data.ts";
import { buildExpansion } from "./expansion.ts";
import { buildAtlas } from "./atlas.ts";

export function publicDataPlugin(): Plugin {
  let root = "",
    development = false;
  let loaded: Awaited<ReturnType<typeof loadPublicData>> | undefined;
  return {
    name: "validated-public-analytics-data",
    config(_config, env) {
      development = env.command === "serve" && !env.isPreview;
    },
    configResolved(config) {
      root = resolve(config.root, "../data");
    },
    async buildStart() {
      loaded = await loadPublicData(resolve(root, "public"));
    },
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const pathname = new URL(request.url ?? "/", "http://localhost").pathname;
        const artifact = loaded?.artifacts.find(({ name }) => pathname === `/${name}`);
        if (!artifact) return next();
        response.setHeader(
          "Content-Type",
          artifact.name.endsWith(".csv")
            ? "text/csv; charset=utf-8"
            : artifact.name.endsWith(".txt")
              ? "text/plain; charset=utf-8"
              : "application/json; charset=utf-8",
        );
        response.end(artifact.source);
      });
    },
    resolveId(id) {
      if (
        [
          "virtual:analytics-expansion",
          "virtual:analytics-method",
          "virtual:analytics-content",
          "virtual:analytics-public-data",
          "virtual:analytics-fixtures",
          "virtual:analytics-atlas",
        ].includes(id)
      )
        return `\0${id}`;
    },
    async load(id) {
      if (id === "\0virtual:analytics-expansion") {
        loaded ??= await loadPublicData(resolve(root, "public"));
        const parts = new Intl.DateTimeFormat("en-CA", {
          timeZone: "Asia/Kolkata",
          year: "numeric",
          month: "2-digit",
          day: "2-digit",
        }).formatToParts(new Date());
        const part = (name: string) => parts.find((p) => p.type === name)!.value;
        const asOf = `${part("year")}-${part("month")}-${part("day")}`;
        return `export default ${JSON.stringify(buildExpansion(loaded, asOf))};`;
      }
      if (id === "\0virtual:analytics-method") {
        loaded ??= await loadPublicData(resolve(root, "public"));
        const contentRoot = resolve(root, "../frontend/content/analytics");
        const articles = await loadAnalyticsContent(contentRoot, loaded.catalogue);
        return `export default ${JSON.stringify(await loadAnalyticsMethod(contentRoot, articles))};`;
      }
      if (id === "\0virtual:analytics-content") {
        loaded ??= await loadPublicData(resolve(root, "public"));
        return `export default ${JSON.stringify(await loadAnalyticsContent(resolve(root, "../frontend/content/analytics"), loaded.catalogue))};`;
      }
      if (id === "\0virtual:analytics-atlas") {
        loaded ??= await loadPublicData(resolve(root, "public"));
        return `export default ${JSON.stringify(buildAtlas(loaded))};`;
      }
      if (id === "\0virtual:analytics-public-data") {
        loaded ??= await loadPublicData(resolve(root, "public"));
        return `export default ${JSON.stringify(loaded.catalogue)};`;
      }
      if (id === "\0virtual:analytics-fixtures") {
        // Production never reads the fixture tree, even if it is malformed.
        if (!development) return "export default null;";
        const fixtures = await loadPublicData(resolve(root, "fixtures"), true);
        const csvs = fixtures.artifacts.filter(({ name }) => name.endsWith("data.csv"));
        return `export default ${JSON.stringify({ catalogue: fixtures.catalogue, csvs, atlas: buildAtlas(fixtures) })};`;
      }
    },
    generateBundle() {
      for (const artifact of loaded?.artifacts ?? [])
        this.emitFile({ type: "asset", fileName: artifact.name, source: artifact.source });
    },
  };
}
