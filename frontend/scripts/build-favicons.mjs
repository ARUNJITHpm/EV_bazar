// Rasterise the Cw mark into dist/ at build time: favicon.ico and the touch
// icons. The sources are SVG text in brand/ (written by
// design/brand/mark/build_mark.py from the design canvas's own font), so no
// binary image is ever committed - the Hugging Face mirror refuses raw
// binaries, and *.png in this repo is LFS reference material the mirror drops.
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { Resvg } from "@resvg/resvg-js";

const root = resolve(import.meta.dirname, "..");
const dist = resolve(root, "dist");

async function png(mark, size) {
  const svg = await readFile(resolve(root, "brand", `mark-${mark}.svg`), "utf8");
  return Buffer.from(new Resvg(svg, { fitTo: { mode: "width", value: size } }).render().asPng());
}

// An ICO is a directory of images; every modern reader accepts PNG entries,
// so each size is its own hand-drawn mark rather than one image scaled.
function ico(entries) {
  const header = Buffer.alloc(6);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2); // type: icon
  header.writeUInt16LE(entries.length, 4);
  let offset = 6 + 16 * entries.length;
  const dir = entries.map(({ size, data }) => {
    const e = Buffer.alloc(16);
    e.writeUInt8(size >= 256 ? 0 : size, 0);
    e.writeUInt8(size >= 256 ? 0 : size, 1);
    e.writeUInt16LE(1, 4); // colour planes
    e.writeUInt16LE(32, 6); // bits per pixel
    e.writeUInt32LE(data.length, 8);
    e.writeUInt32LE(offset, 12);
    offset += data.length;
    return e;
  });
  return Buffer.concat([header, ...dir, ...entries.map((e) => e.data)]);
}

await mkdir(dist, { recursive: true });
await writeFile(
  resolve(dist, "favicon.ico"),
  ico([
    { size: 16, data: await png("16", 16) },
    { size: 32, data: await png("32", 32) },
    { size: 48, data: await png("64", 48) },
  ]),
);
// iOS rounds the corners itself, so the touch mark is a full square.
await writeFile(resolve(dist, "apple-touch-icon.png"), await png("touch", 180));
await writeFile(resolve(dist, "icon-512.png"), await png("touch", 512));
console.log("Favicons: favicon.ico (16, 32, 48), apple-touch-icon.png, icon-512.png");
