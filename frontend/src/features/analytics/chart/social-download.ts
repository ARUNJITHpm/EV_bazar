import {
  assertSocialSvgLegibility,
  socialFormats,
  socialSvg,
  socialTokens,
  type SocialImageInput,
  type SocialPalette,
} from "./social";
import { pngWithProvenance } from "./social-png";
const base64 = (bytes: Uint8Array) => {
  let text = "";
  for (const byte of bytes) text += String.fromCharCode(byte);
  return btoa(text);
};
let fonts: Promise<{ serif: string; mono: string }> | undefined;
function loadFonts() {
  return (fonts ??= Promise.all(
    ["SourceSerif4", "IBMPlexMono"].map(async (name) => {
      const response = await fetch(`/analytics-fonts/${name}.ttf`);
      if (!response.ok) throw new Error("Image fonts could not be loaded. Please retry.");
      return base64(new Uint8Array(await response.arrayBuffer()));
    }),
  )
    .then(([serif, mono]) => ({ serif: serif!, mono: mono! }))
    .catch((error) => {
      fonts = undefined;
      throw error;
    }));
}
export async function downloadSocialImage(input: Omit<SocialImageInput, "fonts" | "palette">) {
  const styles = getComputedStyle(document.documentElement);
  const palette = Object.fromEntries(
    Object.entries(socialTokens).map(([key, token]) => [
      key,
      styles.getPropertyValue(token).trim(),
    ]),
  ) as unknown as SocialPalette;
  const svg = socialSvg({ ...input, palette, fonts: await loadFonts() });
  assertSocialSvgLegibility(svg, input.format);
  const image = new Image();
  // Data URI keeps font resources inside this SVG; no remote requests or tainted canvas.
  image.src = `data:image/svg+xml;base64,${base64(new TextEncoder().encode(svg))}`;
  await image.decode();
  const canvas = document.createElement("canvas"),
    format = socialFormats[input.format];
  canvas.width = format.width;
  canvas.height = format.height;
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Your browser could not prepare an image");
  context.drawImage(image, 0, 0);
  const blob = await new Promise<Blob>((resolve, reject) =>
    canvas.toBlob(
      (value) => (value ? resolve(value) : reject(new Error("Image export failed"))),
      "image/png",
    ),
  );
  const bytes = pngWithProvenance(new Uint8Array(await blob.arrayBuffer()), svg);
  const href = URL.createObjectURL(
    new Blob([bytes as Uint8Array<ArrayBuffer>], { type: "image/png" }),
  );
  try {
    const anchor = document.createElement("a");
    anchor.href = href;
    anchor.download = `${input.data.id}-${input.format}.png`;
    anchor.click();
  } finally {
    setTimeout(() => URL.revokeObjectURL(href), 1000);
  }
}
