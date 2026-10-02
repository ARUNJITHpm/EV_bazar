// @vitest-environment node
import { cp, mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { build } from "vite";
import { expect, it } from "vitest";
import { publicDataPlugin } from "./public-data-plugin";

it("builds public content when the frontend directory is named build, as in Docker", async () => {
  const directory = await mkdtemp(resolve(tmpdir(), "analytics-docker-layout-"));
  const root = resolve(directory, "build");
  try {
    await mkdir(root);
    await cp(fileURLToPath(new URL("../content", import.meta.url)), resolve(root, "content"), {
      recursive: true,
    });
    await cp(
      fileURLToPath(new URL("../../data/public", import.meta.url)),
      resolve(directory, "data/public"),
      { recursive: true },
    );
    const entry = resolve(root, "entry.js");
    await writeFile(
      entry,
      'import articles from "virtual:analytics-content"; import method from "virtual:analytics-method"; console.log(articles, method);',
    );
    const result = await build({
      configFile: false,
      root,
      plugins: [publicDataPlugin()],
      logLevel: "silent",
      build: { write: false, minify: false, rollupOptions: { input: entry } },
    });
    expect("output" in result).toBe(true);
    if ("output" in result) {
      const chunk = result.output.find((item) => item.type === "chunk");
      expect(chunk?.code).toContain("Archived district entries");
    }
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}, 30_000);
