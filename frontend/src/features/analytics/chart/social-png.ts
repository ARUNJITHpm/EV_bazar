// PNG iTXt provenance is shared by browser canvas and the offline PNG renderer.
export function pngWithProvenance(png: Uint8Array, svg: string): Uint8Array {
  if (png.length < 20 || png[0] !== 137 || png[1] !== 80 || png[2] !== 78 || png[3] !== 71)
    throw new Error("Invalid PNG image");
  const metadata = /<metadata>([\s\S]*?)<\/metadata>/.exec(svg)?.[1];
  if (!metadata) throw new Error("Image provenance is missing");
  const json = metadata
    .replaceAll("&quot;", '\"')
    .replaceAll("&gt;", ">")
    .replaceAll("&lt;", "<")
    .replaceAll("&amp;", "&");
  JSON.parse(json);
  const encoder = new TextEncoder();
  const payload = encoder.encode(`Chargeworthy Data\0\0\0\0\0${json}`);
  const type = encoder.encode("iTXt"),
    chunk = new Uint8Array(payload.length + 12);
  new DataView(chunk.buffer).setUint32(0, payload.length);
  chunk.set(type, 4);
  chunk.set(payload, 8);
  let crc = 0xffffffff;
  for (const byte of chunk.subarray(4, -4)) {
    crc ^= byte;
    for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (crc & 1 ? 0xedb88320 : 0);
  }
  new DataView(chunk.buffer).setUint32(chunk.length - 4, (crc ^ 0xffffffff) >>> 0);
  const end = png.length - 12;
  if (new TextDecoder().decode(png.subarray(end + 4, end + 8)) !== "IEND")
    throw new Error("PNG has no terminal IEND");
  const result = new Uint8Array(png.length + chunk.length);
  result.set(png.subarray(0, end));
  result.set(chunk, end);
  result.set(png.subarray(end), end + chunk.length);
  return result;
}
