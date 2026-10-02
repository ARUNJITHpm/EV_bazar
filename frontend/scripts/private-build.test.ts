import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { it, expect } from "vitest";
import { scanPrivateBuild } from "./private-build";

it("checks private values in bundles, maps and binary images without exposing them in errors", async () => {
  const root = await mkdtemp(join(tmpdir(), "private-build-"));
  try {
    for (const file of ["bundle.js", "source.map", "share.png"]) {
      await writeFile(join(root, file), "PrivateOwnerLaunchCanary");
      await expect(scanPrivateBuild(root)).rejects.toThrow(
        "Private record value in built artifact",
      );
      await rm(join(root, file));
    }
    await writeFile(join(root, "bundle.js"), 'const name="Private station 9d2f";');
    await expect(scanPrivateBuild(root, { name: "Private station 9d2f" })).rejects.toThrow(
      "bundle.js",
    );
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

it("allows owner form code, but refuses private fields and short numeric IDs in public data", async () => {
  const root = await mkdtemp(join(tmpdir(), "private-build-"));
  try {
    await writeFile(join(root, "owner.js"), "station_id connected_load_kw phone");
    expect((await scanPrivateBuild(root)).artifacts).toBe(1);
    await mkdir(join(root, "data"));
    await writeFile(join(root, "data", "index.html"), '{"station_id":1}');
    await expect(scanPrivateBuild(root)).rejects.toThrow("Private owner field");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});
