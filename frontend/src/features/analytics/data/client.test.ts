// @vitest-environment node
import { loadPublicData } from "../../../../scripts/public-data";
import { webcrypto } from "node:crypto";
import { fileURLToPath } from "node:url";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadPublicCsv } from "./client";

beforeEach(() => vi.stubGlobal("crypto", webcrypto));
afterEach(() => vi.unstubAllGlobals());

describe("validated public CSV client", () => {
  it("returns null for an unsourced dataset without making a request", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    expect(await loadPublicCsv("ev_registrations")).toBeNull();
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("loads the typed district rows only when the bytes match the build checksum", async () => {
    const loaded = await loadPublicData(
      fileURLToPath(new URL("../../../../../data/public", import.meta.url)),
    );
    const source = loaded.artifacts.find(
      (a) => a.name === "analytics-data/district_reference/data.csv",
    )!.source;
    expect(source).toContain("# Chargeworthy Data: ");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(source)));
    const districts = await loadPublicCsv("district_reference");
    expect(districts?.find((district) => district.lgd_code === 555)?.district_name).toBe(
      "Ernakulam",
    );
  });
  it("refuses altered bytes before using their values", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("tampered data")));
    await expect(loadPublicCsv("district_reference")).rejects.toThrow(
      "differs from its validated build",
    );
  });
});
