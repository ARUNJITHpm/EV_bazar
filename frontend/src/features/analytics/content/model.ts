import type { ChartData } from "../chart/model";
export type ContentBlock =
  | { kind: "paragraph" | "heading"; text: string }
  | { kind: "list"; items: string[] }
  | { kind: "chart"; data: ChartData };
export interface Article {
  slug: string;
  format: "insights" | "weekly";
  title: string;
  question: string;
  summary: string;
  vertical: string;
  authors: string[];
  published_on: string;
  updated_on: string;
  datasets: string[];
  changelog: { date: string; entry: string }[];
  social_caption?: string;
  blocks: ContentBlock[];
}
export const articleHref = (article: Article) => `/data/${article.format}/${article.slug}`;
export function sortedArticles(
  articles: readonly Article[],
  format: Article["format"],
  vertical = "",
) {
  return articles
    .filter((a) => a.format === format && (!vertical || a.vertical === vertical))
    .sort((a, b) => b.published_on.localeCompare(a.published_on) || a.slug.localeCompare(b.slug));
}
