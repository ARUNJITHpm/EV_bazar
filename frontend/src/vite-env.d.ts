/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Mapbox PUBLIC token (pk.), injected at build time. See mapCore.ts. */
  readonly VITE_MAPBOX_TOKEN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
