import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
// vitest/config re-exports Vite's defineConfig with the `test` key added.
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
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
