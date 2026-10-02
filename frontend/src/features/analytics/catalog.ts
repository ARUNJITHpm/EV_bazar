import articles from "virtual:analytics-content";
import { articleHref } from "./content/model";
export const verticals = [
  {
    slug: "vehicles",
    title: "Vehicles",
    description: "EV registrations by district, month and vehicle class.",
    preparation:
      "Registration series and district mappings are being checked. They will appear once their sources and reporting periods are verified.",
  },
  {
    slug: "charging-network",
    title: "Charging network",
    description: "Public chargers, AC and DC coverage, and chargers per 1,000 EVs.",
    preparation:
      "A sourced public charger list is being prepared. Coverage will appear after records are checked and duplicate stations are reconciled.",
  },
  {
    slug: "electricity",
    title: "Electricity",
    description: "EV electricity tariffs, fixed charges and time-of-day rules.",
    preparation:
      "State tariff orders are being reviewed. Rates will appear with their effective dates and source orders once verified.",
  },
  {
    slug: "usage",
    title: "Usage",
    description: "Estimated charging energy, with ranges and sample sizes.",
    preparation:
      "Anonymous district estimates will appear only after enough consenting stations contribute and the privacy and model checks pass.",
  },
  {
    slug: "corridors",
    title: "Corridors",
    description: "Highway stretches without a public fast charger.",
    preparation:
      "Highway lines and charger locations are being checked. Corridor coverage will appear once both datasets are ready.",
  },
  {
    slug: "method",
    title: "Method",
    description: "Where the data comes from, what it can tell us, and what it cannot.",
    preparation:
      "Source notes and methods will grow with each published dataset. Read the methodology page for the publication rules already in place.",
  },
] as const;

export interface SearchEntry {
  title: string;
  description: string;
  href: string;
  kind: "Topic" | "Insight" | "Weekly chart" | "District";
}

// Only registered public content belongs here. Districts and articles are
// added when their verified catalogues exist, never from private owner data.
export const searchEntries: readonly SearchEntry[] = [
  ...articles.map((a): SearchEntry => ({
    title: a.title,
    description: a.summary,
    href: articleHref(a),
    kind: a.format === "insights" ? "Insight" : "Weekly chart",
  })),
  ...verticals.map((vertical): SearchEntry => ({
    title: vertical.title,
    description: vertical.description,
    href: `/data/${vertical.slug}`,
    kind: "Topic",
  })),
  ...publicCatalogue.districts.map((district): SearchEntry => ({
    title: district.district_name,
    description: `${district.state_name}${district.former_names.length ? ` · ${district.former_names.join(", ")}` : ""}`,
    href: `/data/district/${district.slug}`,
    kind: "District",
  })),
];

export function searchPublicContent(
  query: string,
  kind?: SearchEntry["kind"],
): readonly SearchEntry[] {
  const term = query.trim().toLocaleLowerCase("en-IN");
  return searchEntries.filter(
    (entry) =>
      (!kind || entry.kind === kind) &&
      (!term ||
        `${entry.title} ${entry.kind === "District" ? entry.description : ""}`
          .toLocaleLowerCase("en-IN")
          .includes(term)),
  );
}

export const staticAnalyticsPaths = [
  ...articles.map(articleHref),
  "/data",
  ...verticals.map(({ slug }) => `/data/${slug}`),
  "/data/district",
  "/data/insights",
  "/data/weekly",
  "/data/methodology",
  "/data/sources",
  ...publicCatalogue.districts.map(({ slug }) => `/data/district/${slug}`),
];

export function analyticsMetadata(pathname: string) {
  const path = pathname.replace(/\/+$/, "") || "/";
  const vertical = verticals.find(({ slug }) => path === `/data/${slug}`);
  const district = publicCatalogue.districts.find(({ slug }) => path === `/data/district/${slug}`);
  const titles: Record<string, string> = {
    "/data": "Chargeworthy Data",
    "/data/district": "District data",
    "/data/insights": "Insights",
    "/data/weekly": "One question, one chart",
    "/data/methodology": "Methodology",
    "/data/sources": "Sources",
  };
  const article = articles.find((a) => articleHref(a) === path);
  const title =
    article?.title ??
    (district
      ? `${district.district_name}, ${district.state_name} (LGD ${district.lgd_code})`
      : undefined) ??
    vertical?.title ??
    titles[path] ??
    "Data being prepared";
  return {
    title:
      title === "Chargeworthy Data"
        ? `${title} — EV charging in India`
        : `${title} — Chargeworthy Data`,
    description:
      article?.summary ??
      (district
        ? `Available EV charging context for ${district.district_name}, ${district.state_name}, LGD ${district.lgd_code}. Sources, coverage and missing data are listed explicitly.`
        : undefined) ??
      vertical?.description ??
      `${titles[path] ?? "Unpublished page"}: public EV charging data for India, with transparent sources, coverage and methods.`,
    // Shells contain no published indicators yet. Remove only as real
    // datasets/content are published, including the district-specific gate.
    noindex:
      path === "/data/methodology" ||
      path === "/data/sources" ||
      article ||
      ((path === "/data/insights" || path === "/data/weekly") &&
        articles.some((a) => path === `/data/${a.format}`))
        ? false
        : district
          ? !hasDistrictIndicator(atlas, district)
          : path !== "/data",
  };
}
import publicCatalogue from "virtual:analytics-public-data";

import atlas from "virtual:analytics-atlas";
import { hasDistrictIndicator } from "./districts/model";
