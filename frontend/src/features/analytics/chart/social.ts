import { CW_MARK_BOX, CW_MARK_PATH } from "../../public/cwMarkGlyphs";
import { numberLabel, validateChart, valueDomain, type ChartData, type ChartRow } from "./model";

export const socialFormats = {
  portrait: { width: 1080, height: 1350, label: "Instagram portrait", minFont: 36, maxRows: 6 },
  square: { width: 1080, height: 1080, label: "Square", minFont: 36, maxRows: 3 },
  og: { width: 1200, height: 630, label: "Open Graph", minFont: 40, maxRows: 1 },
} as const;
export type SocialFormat = keyof typeof socialFormats;
// v2: the Cw mark joined the brand line (2026-10-03).
export const socialRendererVersion = "analytics_social_v2";
export interface SocialPalette {
  paper: string;
  ink: string;
  muted: string;
  slate: string;
  rule: string;
  highlight: string;
}
export const socialTokens: Record<keyof SocialPalette, string> = {
  paper: "--cw-paper",
  ink: "--cw-ink",
  muted: "--cw-paper-muted",
  slate: "--cw-paper-slate",
  rule: "--cw-rule",
  highlight: "--cw-data-highlight",
};
const escape = (text: string) =>
  text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
// Conservative character widths, never shrinking fonts to fit. The PNG verifier
// also measures actual glyph bounds using the pinned fonts in Chromium.
export function wrapSocialText(
  text: string,
  width: number,
  size: number,
  maxLines: number,
): string[] {
  const limit = Math.floor(width / (size * 0.62));
  if (limit < 1) throw new Error("Image text has no room");
  const lines: string[] = [];
  let line = "";
  for (const word of text.trim().split(/\s+/)) {
    const parts = word.match(new RegExp(`.{1,${limit}}`, "gu")) ?? [];
    for (const part of parts) {
      if (line && line.length + part.length + 1 > limit) {
        lines.push(line);
        line = "";
      }
      line += (line ? " " : "") + part;
    }
  }
  if (line) lines.push(line);
  if (lines.length > maxLines)
    throw new Error(
      "Labels do not fit at a readable size. Choose a larger format or filter this chart.",
    );
  return lines;
}
export function socialImagePath(slug: string, format: SocialFormat) {
  if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) throw new Error("Unsafe social image slug");
  return `/analytics-images/${slug}-${format}.png`;
}
export function assertSocialSvgLegibility(svg: string, format: SocialFormat) {
  const f = socialFormats[format];
  const sizes = [...svg.matchAll(/font-size="([0-9.]+)"/g)].map((m) => Number(m[1]));
  if (
    !sizes.length ||
    sizes.some((size) => !Number.isFinite(size) || size < f.minFont || (size * 300) / f.width < 10)
  )
    throw new Error("Image label below minimum readable font size");
}
export interface SocialImageInput {
  data: ChartData;
  rows: readonly ChartRow[];
  question: string;
  pageUrl: string;
  format: SocialFormat;
  palette: SocialPalette;
  fonts?: { serif: string; mono: string };
}
export function socialSvg({
  data,
  rows,
  question,
  pageUrl,
  format,
  palette,
  fonts,
}: SocialImageInput): string {
  validateChart(data);
  if (!question.trim().endsWith("?"))
    throw new Error("The image title must be a reviewed question");
  if (!/^https?:\/\//.test(pageUrl)) throw new Error("Image needs an absolute page URL");
  if (rows.some((r) => !data.rows.includes(r)))
    throw new Error("Image rows must belong to this chart");
  const f = socialFormats[format],
    og = format === "og",
    pad = 40;
  if (!rows.length) throw new Error("No data matches this selection");
  if (rows.length > f.maxRows)
    throw new Error(
      `This format fits at most ${f.maxRows} rows at a readable size. Filter the chart or choose a larger format.`,
    );
  for (const colour of Object.values(palette))
    if (!/^#[0-9a-f]{6}$/i.test(colour)) throw new Error("Invalid report palette token");
  const parts: string[] = [];
  const text = (
    value: string,
    x: number,
    y: number,
    width: number,
    maxLines = 1,
    size: number = f.minFont,
    mono = false,
    colour = palette.ink,
  ) => {
    if (size < f.minFont || (size * 300) / f.width < 10)
      throw new Error("Image label below minimum readable font size");
    const lines = wrapSocialText(value, width, size, maxLines);
    lines.forEach((line, i) => {
      const baseline = y + i * size * 1.15;
      if (baseline > f.height - 18 || baseline - size < 0)
        throw new Error("Image text exceeds the format bounds");
      parts.push(
        `<text x="${x}" y="${baseline}" font-family="${mono ? "IBM Plex Mono" : "Source Serif 4"}" font-size="${size}" fill="${colour}">${escape(line)}</text>`,
      );
    });
    return lines.length;
  };
  const available = rows.filter((r) => r.value !== null);
  const key = available.reduce<ChartRow | undefined>(
    (best, row) => (!best || row.value! > best.value! ? row : best),
    undefined,
  );
  // The Cw mark, paper version (design/brand/mark/), centred on the cap
  // height of the brand line beside it. Same glyphs as the report's head.
  const brandSize = og ? 40 : 44,
    brandBaseline = og ? 54 : 68,
    markTop = brandBaseline - brandSize * 0.34 - brandSize / 2,
    brandX = pad + brandSize + 16;
  parts.push(
    `<g transform="translate(${pad} ${markTop.toFixed(2)}) scale(${(brandSize / CW_MARK_BOX).toFixed(4)})"><rect x="0.5" y="0.5" width="${CW_MARK_BOX - 1}" height="${CW_MARK_BOX - 1}" rx="5.5" fill="${palette.paper}" stroke="${palette.rule}" stroke-width="1"/><path d="${CW_MARK_PATH}" fill="${palette.slate}"/></g>`,
  );
  text(
    ["localhost", "127.0.0.1", "[::1]"].includes(new URL(pageUrl).hostname)
      ? "Chargeworthy Data \u00b7 Local preview"
      : "Chargeworthy Data",
    brandX,
    brandBaseline,
    f.width - pad - brandX,
    1,
    brandSize,
  );
  text(question, pad, og ? 122 : 152, og ? 620 : 1000, og ? 4 : 3, og ? 48 : 56);
  // Keep the period on the image: retrieval date is not the observation period.
  text(
    data.social?.context ?? data.subtitle,
    pad,
    og ? 352 : 350,
    og ? 620 : 1000,
    og ? 2 : 3,
    f.minFont,
    false,
    palette.muted,
  );
  const kx = og ? 700 : pad,
    ky = og ? 140 : format === "portrait" ? 500 : 466;
  text(key ? numberLabel(key.value!) : "No data", kx, ky, og ? 460 : 1000, 1, og ? 80 : 100, true);
  text(
    key
      ? `${rows.length === 1 ? "" : `${key.label} \u00b7 `}${data.unit}${key.status === "estimate" ? " \u00b7 P50 estimate" : ""}`
      : "Not enough data yet",
    kx,
    ky + (og ? 58 : 60),
    og ? 460 : 1000,
    og ? 2 : 2,
  );
  if (key?.status === "estimate")
    text(
      `P10 ${numberLabel(key.p10!)} \u2013 P90 ${numberLabel(key.p90!)}`,
      kx,
      ky + 144,
      og ? 460 : 1000,
      2,
      f.minFont,
      true,
    );
  const top = og ? 304 : format === "portrait" ? 690 : 650,
    bottom = og ? 374 : format === "portrait" ? 980 : 790;
  const left = og ? 700 : 360,
    right = f.width - pad,
    [min, max] = valueDomain(rows);
  const scale = (v: number) => left + ((v - min) / (max - min)) * (right - left);
  if (key?.status === "estimate") {
    const rangeLines = wrapSocialText(
      `P10 ${numberLabel(key.p10!)} \u2013 P90 ${numberLabel(key.p90!)}`,
      og ? 460 : 1000,
      f.minFont,
      2,
    ).length;
    const rangeBottom = ky + 144 + (rangeLines - 1) * f.minFont * 1.15 + 12;
    if (rangeBottom > top - (og ? 0 : rows.length === 1 ? 60 : 0))
      throw new Error(
        "The estimate range needs more room. Choose a larger format or filter this chart.",
      );
  }
  const step = (bottom - top) / rows.length;
  if (step < f.minFont * 1.15)
    throw new Error(
      "Chart labels overlap at the minimum font size. Filter this selection or choose a larger format.",
    );
  const manySeries = new Set(rows.map((r) => r.series)).size > 1;
  // All formats use a horizontal comparison. Each mark retains its original
  // category, value and interval; line charts are labelled as period comparisons.
  rows.forEach((r, i) => {
    const y = top + (i + 0.5) * step;
    if (!og)
      text(
        manySeries ? `${r.series}: ${r.label}` : r.label,
        pad,
        rows.length === 1 ? top - 22 : y + 12,
        rows.length === 1 ? 1000 : 300,
        1,
      );
    if (r.value === null) {
      text("No data", left, y + 12, right - left, 1, f.minFont, false, palette.muted);
      return;
    }
    if (data.type === "line" || data.type === "small-multiples") {
      const previous = rows[i - 1];
      if (previous?.value != null && previous.series === r.series)
        parts.push(
          `<line x1="${scale(previous.value)}" x2="${scale(r.value)}" y1="${y - step}" y2="${y}" stroke="${palette.slate}" stroke-width="4"/>`,
        );
    }
    if (r.status === "estimate") {
      parts.push(
        `<line x1="${scale(r.p10!)}" x2="${scale(r.p90!)}" y1="${y}" y2="${y}" stroke="${palette.slate}" stroke-width="12"/><circle cx="${scale(r.value)}" cy="${y}" r="10" fill="${palette.highlight}"/>`,
      );
    } else if (data.type === "line" || data.type === "small-multiples")
      parts.push(`<circle cx="${scale(r.value)}" cy="${y}" r="10" fill="${palette.slate}"/>`);
    else
      parts.push(
        `<rect x="${Math.min(scale(0), scale(r.value))}" y="${y - 12}" width="${Math.max(2, Math.abs(scale(r.value) - scale(0)))}" height="24" fill="${palette.slate}"/>`,
      );
    if (og && rows.length > 1) text(r.label, left, y - 16, right - left, 1);
  });
  parts.push(
    `<line x1="${left}" x2="${right}" y1="${bottom + 8}" y2="${bottom + 8}" stroke="${palette.ink}" stroke-width="2"/>`,
  );
  text(numberLabel(min), left, bottom + 49, 260, 1, f.minFont, true);
  const high = numberLabel(max);
  text(high, right - high.length * f.minFont * 0.62, bottom + 49, 280, 1, f.minFont, true);
  const footer = og ? 458 : format === "portrait" ? 1100 : 880;
  const credits = `Source: ${data.sources.map((s) => `${s.name} \u00b7 ${s.licence.split(" (")[0]}`).join("; ")}`;
  text(credits, pad, footer, f.width - 2 * pad, 2, f.minFont, false, palette.muted);
  text(
    pageUrl.replace(/^https?:\/\//, ""),
    pad,
    footer + (og ? 96 : 96),
    f.width - 2 * pad,
    og ? 2 : 3,
    f.minFont,
    true,
    palette.slate,
  );
  const metadata = {
    title: question,
    chart: data.title,
    unit: data.unit,
    updated: data.updated,
    sources: data.sources,
    original_content_licence: "CC BY 4.0",
    page_url: pageUrl,
    versions: { ...data.versions, renderer_version: socialRendererVersion },
    chart_renderer_version: data.versions.renderer_version,
    rows,
  };
  const fontStyle = fonts
    ? `<style>@font-face{font-family:'Source Serif 4';src:url(data:font/ttf;base64,${fonts.serif})} @font-face{font-family:'IBM Plex Mono';src:url(data:font/ttf;base64,${fonts.mono})}</style>`
    : "";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${f.width}" height="${f.height}" viewBox="0 0 ${f.width} ${f.height}" role="img"><title>${escape(question)}</title><desc>${escape(data.summary)} ${escape(rows.map((r) => `${r.series}, ${r.label}: ${r.value === null ? "Not enough data yet" : r.status === "estimate" ? `P10 ${r.p10}, P50 ${r.value}, P90 ${r.p90}` : r.value}`).join("; "))}</desc><metadata>${escape(JSON.stringify(metadata))}</metadata>${fontStyle}<rect width="100%" height="100%" fill="${palette.paper}"/>${parts.join("")}</svg>`;
}
