import { fileURLToPath, URL } from "node:url";
import { stat } from "node:fs/promises";
import { resolve } from "node:path";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
// vitest/config re-exports Vite's defineConfig with the `test` key added.
import { defineConfig } from "vitest/config";
import { publicDataPlugin } from "./scripts/public-data-plugin";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    publicDataPlugin(),
    {
      name: "analytics-preview-documents",
      configurePreviewServer(server) {
        server.middlewares.use(async (request, _response, next) => {
          const url = new URL(request.url ?? "/", "http://localhost");
          if (!/^\/data(?:\/[a-z0-9-]+)*\/?$/.test(url.pathname)) return next();
          const path = url.pathname.replace(/\/+$/, "");
          const document = `${path}/index.html`;
          try {
            await stat(resolve(server.config.root, server.config.build.outDir, `.${document}`));
            request.url = `${document}${url.search}`;
          } catch {
            const group = path.split("/")[2];
            const fallback = ["district", "insights", "weekly"].includes(group ?? "")
              ? `/data/${group}/index.html`
              : "/data/fallback.html";
            request.url = `${fallback}${url.search}`;
          }
          next();
        });
      },
    },
  ],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    // Dev only. In production Caddy serves dist/ and proxies /api, so the
    // SPA and the API are same-origin and this proxy does not exist.
    proxy: {
      "/api": {
        // http://api:8000 under docker compose, localhost when run bare.
        target: process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
    // Rule 1: the manifest gives us the build hash that becomes
    // renderer_version on every report. See STACK.md section 6.
    manifest: true,
    sourcemap: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
