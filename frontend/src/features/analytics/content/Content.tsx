import { Fragment, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import articles from "virtual:analytics-content";
import { Chart } from "../chart/Chart";
import { verticals } from "../catalog";
import { articleHref, sortedArticles, type Article } from "./model";
import "./content.css";
function Inline({ text }: { text: string }) {
  const pieces = text.split(/(\[[^\]]+\]\([^)]+\))/g);
  return (
    <>
      {pieces.map((piece, i) => {
        const match = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(piece);
        return (
          <Fragment key={i}>
            {match ? (
              match[2]!.startsWith("/data") ? (
                <Link to={match[2]!}>{match[1]}</Link>
              ) : (
                <a href={match[2]}>{match[1]}</a>
              )
            ) : (
              piece
            )}
          </Fragment>
        );
      })}
    </>
  );
}
export function ArticleList({ entries }: { entries: readonly Article[] }) {
  return (
    <ul className="analytics-content-list">
      {entries.map((article) => (
        <li key={articleHref(article)}>
          <h3>
            <Link to={articleHref(article)}>{article.title}</Link>
          </h3>
          <p>
            <time dateTime={article.published_on}>{article.published_on}</time> ·{" "}
            {verticals.find((v) => v.slug === article.vertical)?.title}
          </p>
          {article.format === "insights" && <p>{article.summary}</p>}
        </li>
      ))}
    </ul>
  );
}
export function ContentIndex({ format }: { format: Article["format"] }) {
  const [params] = useSearchParams();
  const [enhanced, setEnhanced] = useState(false);
  useEffect(() => setEnhanced(true), []);
  const selected = enhanced ? (params.get("vertical") ?? "") : "";
  const entries = sortedArticles(articles, format, selected);
  return (
    <>
      <p>
        {format === "insights"
          ? "Living articles answering one question with sourced charts."
          : "One question, one chart, with a short explanation and a source you can check."}
      </p>
      <nav aria-label="Filter by vertical" className="analytics-content-filters">
        {[{ slug: "", title: "All topics" }, ...verticals].map((v) => {
          const next = new URLSearchParams(enhanced ? params : undefined);
          if (v.slug) next.set("vertical", v.slug);
          else next.delete("vertical");
          return (
            <Link
              key={v.slug}
              to={`?${next}`}
              aria-current={selected === v.slug ? "page" : undefined}
            >
              {v.title}
            </Link>
          );
        })}
      </nav>
      <p role="status">
        {entries.length.toLocaleString("en-IN")} published {entries.length === 1 ? "post" : "posts"}
      </p>
      {entries.length ? (
        <ArticleList entries={entries} />
      ) : (
        <p>
          No posts have been published in this topic yet. They will appear when their sources and
          explanations have been reviewed.
        </p>
      )}
    </>
  );
}
export function ContentArticle({ format }: { format: Article["format"] }) {
  const { slug } = useParams();
  const article = articles.find((a) => a.format === format && a.slug === slug);
  if (!article)
    return (
      <>
        <h1>Article unavailable</h1>
        <p>This article has not been published.</p>
        <Link to={`/data/${format}`}>Browse published posts</Link>
      </>
    );
  return (
    <article className="analytics-article">
      <nav aria-label="Breadcrumb" className="analytics-breadcrumb">
        <Link to="/data">Data</Link>
        <span>/</span>
        <Link to={`/data/${format}`}>{format === "insights" ? "Insights" : "Weekly"}</Link>
      </nav>
      <p className="analytics-label">{verticals.find((v) => v.slug === article.vertical)?.title}</p>
      <h1>{article.title}</h1>
      {format === "insights" && <p className="analytics-lead">{article.summary}</p>}
      <p>
        Published on <time dateTime={article.published_on}>{article.published_on}</time> ·{" "}
        {article.authors.join(", ")}
      </p>
      {format === "insights" && (
        <p className="analytics-content-updated">
          Updated on <time dateTime={article.updated_on}>{article.updated_on}</time>
        </p>
      )}
      {article.blocks.map((block, i) =>
        block.kind === "chart" ? (
          <Chart key={block.data.id} data={block.data} />
        ) : block.kind === "heading" ? (
          <h2 key={i}>{block.text}</h2>
        ) : block.kind === "list" ? (
          <ul key={i}>
            {block.items.map((text, j) => (
              <li key={j}>
                <Inline text={text} />
              </li>
            ))}
          </ul>
        ) : (
          <p key={i}>
            <Inline text={block.text} />
          </p>
        ),
      )}
      {article.social_caption && (
        <details className="analytics-section">
          <summary>Caption for sharing</summary>
          <p>{article.social_caption}</p>
        </details>
      )}
      {format === "insights" && (
        <section className="analytics-section" aria-labelledby="article-changelog">
          <h2 id="article-changelog">Changelog</h2>
          <ol>
            {[...article.changelog]
              .sort((a, b) => b.date.localeCompare(a.date))
              .map((c, i) => (
                <li key={i}>
                  <time dateTime={c.date}>{c.date}</time> — {c.entry}
                </li>
              ))}
          </ol>
        </section>
      )}
      <p>
        Datasets used:{" "}
        {article.datasets.map((dataset, i) => (
          <Fragment key={dataset}>
            {i > 0 && ", "}
            <Link to="/data/sources">{dataset.replaceAll("_", " ")}</Link>
          </Fragment>
        ))}
      </p>
    </article>
  );
}
export function LatestWeekly() {
  const latest = sortedArticles(articles, "weekly")[0];
  const chart = latest?.blocks.find((b) => b.kind === "chart");
  return latest && chart?.kind === "chart" ? (
    <>
      <h3>
        <Link to={articleHref(latest)}>{latest.title}</Link>
      </h3>
      <Chart data={chart.data} />
    </>
  ) : (
    <p>The first weekly chart will appear when its sources are reviewed.</p>
  );
}
export function RecentInsights() {
  return <ArticleList entries={sortedArticles(articles, "insights").slice(0, 3)} />;
}
export function TopicList() {
  return (
    <section className="analytics-section">
      <h2>All topics and posts</h2>
      <ul>
        {verticals.map((v) => (
          <li key={v.slug}>
            <Link to={`/data/${v.slug}`}>{v.title}</Link>
          </li>
        ))}
        {articles.map((a) => (
          <li key={articleHref(a)}>
            <Link to={articleHref(a)}>{a.title}</Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
