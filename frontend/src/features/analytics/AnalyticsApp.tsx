import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Link, Route, Routes, useLocation, useParams } from "react-router-dom";
import publicCatalogue from "virtual:analytics-public-data";
import { developmentFixtures } from "./data/client";
import { parseCsv } from "../../../scripts/csv";

import { analyticsMetadata, searchPublicContent, verticals } from "./catalog";

const ChartDemo = import.meta.env.DEV ? lazy(() => import("./chart/ChartDemo")) : null;

function Preparation({ children }: { children: ReactNode }) {
  return (
    <div className="analytics-preparation">
      <p className="analytics-label">Being prepared</p>
      <p>{children}</p>
    </div>
  );
}

function Search({ districtsOnly = false }: { districtsOnly?: boolean }) {
  const [query, setQuery] = useState("");
  const matches =
    districtsOnly && !query.trim()
      ? []
      : searchPublicContent(query, districtsOnly ? "District" : query.trim() ? undefined : "Topic");
  const id = districtsOnly ? "district-search" : "data-search";
  return (
    <section className="analytics-section" aria-labelledby={`${id}-heading`}>
      <h2 id={`${id}-heading`}>{districtsOnly ? "Find your district" : "Find a topic"}</h2>
      <p id={`${id}-help`}>
        {districtsOnly
          ? publicCatalogue.districts.length
            ? "Search district names or states in our archived LGD reference. District boundaries and names may have changed since this snapshot; indicators will appear after their sources are verified."
            : "District search will open once a sourced district reference is available."
          : "Search topic titles. Insights, weekly charts and districts will join this index as they are published."}
      </p>
      <label htmlFor={id}>{districtsOnly ? "District name" : "Search Chargeworthy Data"}</label>
      <input
        id={id}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        aria-describedby={`${id}-help`}
        placeholder={
          districtsOnly
            ? publicCatalogue.districts.length
              ? "Try Ernakulam or Kerala"
              : "District search is being prepared"
            : "Try Electricity or Vehicles"
        }
        disabled={districtsOnly && publicCatalogue.districts.length === 0}
      />
      {(!districtsOnly || query.trim()) && (
        <>
          <p className="analytics-search-status" role="status">
            {matches.length === 0
              ? "No matching titles. Try another topic."
              : `${matches.length.toLocaleString("en-IN")} ${matches.length === 1 ? "result" : "results"} found`}
          </p>
          <ul className="analytics-search-results" id={`${id}-results`}>
            {matches.slice(0, 20).map((entry) => (
              <li key={entry.href}>
                <Link to={entry.href}>{entry.title}</Link>
                <span>{entry.kind === "District" ? entry.description : entry.kind}</span>
              </li>
            ))}
          </ul>
          {matches.length > 20 && (
            <p>
              Showing the first <span className="analytics-number">20</span> matches. Narrow your
              search to find a district.
            </p>
          )}
          <noscript>
            <p>Search needs JavaScript. You can browse every topic using the links on this page.</p>
          </noscript>
        </>
      )}
    </section>
  );
}

function Landing() {
  return (
    <>
      <p className="analytics-label">Public knowledge · India</p>
      <h1>Chargeworthy Data</h1>
      <p className="analytics-lead">EV charging in India, explained through data.</p>
      <p className="analytics-intro">
        Explore registrations, charging coverage and electricity costs, with sources you can check.
        Our original content is free to use under CC BY 4.0; source datasets retain their own
        licences.
      </p>
      <section className="analytics-section" aria-labelledby="latest-weekly">
        <p className="analytics-label">One question, one chart</p>
        <h2 id="latest-weekly">The weekly chart</h2>
        <Preparation>
          Our first weekly chart will appear here after its dataset is verified and the accompanying
          explanation is published.
        </Preparation>
        <Link className="analytics-text-link" to="/data/weekly">
          About the weekly series <span aria-hidden="true">→</span>
        </Link>
      </section>
      <section className="analytics-section" aria-labelledby="topics-heading">
        <h2 id="topics-heading">Explore the topics</h2>
        <ol className="analytics-topics">
          {verticals.map((vertical, index) => (
            <li key={vertical.slug}>
              <span className="analytics-topic-number" aria-hidden="true">
                {String(index + 1).padStart(2, "0")}
              </span>
              <div>
                <h3>
                  <Link to={`/data/${vertical.slug}`}>{vertical.title}</Link>
                </h3>
                <p>{vertical.description}</p>
              </div>
              <span aria-hidden="true">↗</span>
            </li>
          ))}
        </ol>
      </section>
      <section className="analytics-section" aria-labelledby="insights-heading">
        <h2 id="insights-heading">Recent insights</h2>
        <Preparation>
          Articles will appear here when their sourced charts and explanations are ready. Each
          article will show its publication date, updates and corrections.
        </Preparation>
        <Link className="analytics-text-link" to="/data/insights">
          About the insights <span aria-hidden="true">→</span>
        </Link>
      </section>
      <Search districtsOnly />
      <Search />
    </>
  );
}

function DocumentPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <>
      <nav className="analytics-breadcrumb" aria-label="Breadcrumb">
        <Link to="/data">Data</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{title}</span>
      </nav>
      <h1>{title}</h1>
      {children}
    </>
  );
}

function DistrictPage() {
  const { slug } = useParams();
  const district = publicCatalogue.districts.find((district) => district.slug === slug);
  const reference = publicCatalogue.datasets.find((dataset) => dataset.id === "district_reference");
  return (
    <DocumentPage title={district?.district_name ?? "District data"}>
      {district && (
        <>
          <p className="analytics-lead">{district.state_name}</p>
          <p>
            District name and LGD code <span className="analytics-number">{district.lgd_code}</span>{" "}
            come from our archived reference, retrieved{" "}
            <time>{reference?.metadata.retrieved_on}</time>. This is not a claim of current district
            coverage. <Link to="/data/sources">See the source and vintage.</Link>
          </p>
        </>
      )}
      <Preparation>
        District indicators are being prepared. Registrations, public charging coverage and
        electricity tariffs will appear after their source datasets are verified. Usage estimates
        will appear only when privacy and validation checks pass.
      </Preparation>
      <h2>What we don’t know yet</h2>
      <p>
        No district indicators have been published here yet. Missing data will always be labelled,
        never shown as zero.
      </p>
    </DocumentPage>
  );
}

function InsightsPage() {
  return (
    <DocumentPage title="Insights">
      <Preparation>
        Our first insights are being prepared. Articles answering a question with sourced charts
        will appear once their datasets are checked and their explanations are published.
      </Preparation>
      <p>Every article will carry an update date and a record of changes.</p>
    </DocumentPage>
  );
}

function WeeklyPage() {
  return (
    <DocumentPage title="One question, one chart">
      <Preparation>
        The first weekly post is being prepared. It will appear when its public dataset is verified,
        with one chart, a short explanation and a source you can follow.
      </Preparation>
      <p>Each published chart will include a table view and downloadable data.</p>
    </DocumentPage>
  );
}

function MethodologyPage() {
  return (
    <DocumentPage title="Methodology">
      <p className="analytics-lead">Know what a number can tell you.</p>
      <p>
        Every published chart will identify its source, reporting period and last update. Estimates
        will carry a range, and missing observations will be labelled.
      </p>
      <h2>Owner data stays private</h2>
      <ul>
        <li>Only stations whose owners gave analysis consent are eligible.</li>
        <li>Shared and unknown meters are excluded.</li>
        <li>
          A published group must contain at least <span className="analytics-number">10</span>{" "}
          stations.
        </li>
        <li>No station may account for more than one third of the group’s total.</li>
        <li>Groups that fail these checks show “Not enough data yet”, never a number.</li>
      </ul>
      <Preparation>
        Detailed source methods, model validation and limitations will be added alongside the first
        published datasets. No usage model results have been published here yet.
      </Preparation>
      <h2 id="corrections">Corrections</h2>
      <p>
        No corrections have been published yet. Future changes will record what changed, when and
        why.
      </p>
    </DocumentPage>
  );
}

function SourcesPage() {
  return (
    <DocumentPage title="Sources">
      <p>Every dataset will have a source link, retrieval date, reporting period and licence.</p>
      {publicCatalogue.datasets.map((dataset) => (
        <section className="analytics-section" key={dataset.id}>
          <h2>{dataset.metadata.title}</h2>
          <p>
            <a href={dataset.metadata.source_url}>{dataset.metadata.source_name}</a>
          </p>
          <p>
            Retrieved <time>{dataset.metadata.retrieved_on}</time>. {dataset.metadata.time_coverage}
            .
          </p>
          <p>Licence: {dataset.metadata.licence}.</p>
          <p>{dataset.metadata.notes}</p>
        </section>
      ))}
      <Preparation>
        Remaining public datasets are being prepared. Entries will appear once their datasets and
        metadata have been verified.
      </Preparation>
      <p>
        Our original explanations are licensed under{" "}
        <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>. Third-party datasets
        keep their own licences, which will be shown alongside each source and download.
      </p>
    </DocumentPage>
  );
}

function UnpublishedPage() {
  return (
    <DocumentPage title="Data page unavailable">
      <Preparation>
        This page has no published content yet. Districts, insights and weekly charts will appear
        once their sources and publication checks are complete.
      </Preparation>
      <Link className="analytics-text-link" to="/data">
        Explore the available topics <span aria-hidden="true">→</span>
      </Link>
    </DocumentPage>
  );
}

export function AnalyticsApp() {
  const { pathname, search } = useLocation();
  const [fixtureCsv, setFixtureCsv] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    setFixtureCsv(null);
    void developmentFixtures(search).then((fixtures) => {
      if (active)
        setFixtureCsv(
          fixtures?.csvs.find((csv) => csv.name.includes("public_chargers"))?.source ?? null,
        );
    });
    return () => {
      active = false;
    };
  }, [search]);
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  useEffect(() => {
    const previousTitle = document.title;
    const selectors = [
      'meta[name="description"]',
      'meta[property="og:title"]',
      'meta[property="og:description"]',
    ];
    const previousMeta = selectors.map((selector) => ({
      element: document.querySelector(selector),
      content: document.querySelector(selector)?.getAttribute("content") ?? "",
    }));
    const previousRobots = document.querySelector<HTMLMetaElement>('meta[name="robots"]');
    const previousRobotsContent = previousRobots?.content;
    const metadata = analyticsMetadata(pathname);
    document.title = metadata.title;
    document
      .querySelector('meta[name="description"]')
      ?.setAttribute("content", metadata.description);
    let robots = document.querySelector<HTMLMetaElement>('meta[name="robots"]');
    if (!robots) {
      robots = document.createElement("meta");
      robots.name = "robots";
      document.head.append(robots);
    }
    robots.content = metadata.noindex ? "noindex, follow" : "index, follow";
    document.querySelector('meta[property="og:title"]')?.setAttribute("content", metadata.title);
    document
      .querySelector('meta[property="og:description"]')
      ?.setAttribute("content", metadata.description);
    return () => {
      document.title = previousTitle;
      for (const previous of previousMeta)
        previous.element?.setAttribute("content", previous.content);
      if (previousRobots) previousRobots.content = previousRobotsContent ?? "";
      else robots?.remove();
      if (!/^\/data(?:\/|$)/.test(window.location.pathname)) {
        // A visitor can arrive on a prerendered Data document and then go
        // home within the SPA. Do not leave its noindex/title on other routes.
        document.title = "Chargeworthy — will your land pay for a charger?";
        document
          .querySelector('meta[name="description"]')
          ?.setAttribute(
            "content",
            "Independent EV charging site assessment. We tell you whether a location will make money, and match you to the right operator.",
          );
        document
          .querySelector('meta[property="og:title"]')
          ?.setAttribute("content", "Chargeworthy");
        document
          .querySelector('meta[property="og:description"]')
          ?.setAttribute(
            "content",
            "Independent EV charging site assessment. Right site. Right operator.",
          );
        robots?.remove();
      }
    };
  }, [pathname]);
  return (
    <div className="analytics-root">
      <a className="analytics-skip" href="#data-main">
        Skip to content
      </a>
      <header className="analytics-header">
        <span className="analytics-wordmark">Chargeworthy</span>
        <nav aria-label="Data navigation">
          <Link
            to="/data"
            aria-current={pathname.replace(/\/+$/, "") === "/data" ? "page" : undefined}
          >
            Data
          </Link>
          <Link to="/data/methodology">Methodology</Link>
          <Link to="/data/sources">Sources</Link>
        </nav>
      </header>
      <main id="data-main" tabIndex={-1} className="analytics-document">
        {fixtureCsv && (
          <aside aria-label="Test data" className="analytics-preparation">
            <h2>Test data</h2>
            <p>
              Invented fixtures for development only. These are not observations and are never
              published.
            </p>
            <ul>
              {parseCsv(fixtureCsv, "development fixtures")
                .slice(1)
                .map(({ values }, index) => (
                  <li key={index}>{values[1]}</li>
                ))}
            </ul>
          </aside>
        )}
        <Routes>
          {ChartDemo && new URLSearchParams(search).get("fixtures") === "1" && (
            <Route
              path="chart-demo"
              element={
                <Suspense fallback={<p>Loading chart demo…</p>}>
                  <ChartDemo />
                </Suspense>
              }
            />
          )}
          <Route path="/" element={<Landing />} />
          {verticals.map((vertical) => (
            <Route
              key={vertical.slug}
              path={vertical.slug}
              element={
                <DocumentPage title={vertical.title}>
                  <p className="analytics-lead">{vertical.description}</p>
                  <Preparation>{vertical.preparation}</Preparation>
                  {vertical.slug === "method" && (
                    <Link className="analytics-text-link" to="/data/methodology">
                      Read the methodology →
                    </Link>
                  )}
                </DocumentPage>
              }
            />
          ))}
          <Route path="district" element={<DistrictPage />} />
          <Route path="district/:slug" element={<DistrictPage />} />
          <Route path="insights" element={<InsightsPage />} />
          <Route path="insights/:slug" element={<InsightsPage />} />
          <Route path="weekly" element={<WeeklyPage />} />
          <Route path="weekly/:slug" element={<WeeklyPage />} />
          <Route path="methodology" element={<MethodologyPage />} />
          <Route path="sources" element={<SourcesPage />} />
          <Route path="*" element={<UnpublishedPage />} />
        </Routes>
      </main>
      <footer className="analytics-footer">
        <div>
          <span className="analytics-wordmark">Chargeworthy Data</span>
          <p>
            Original content: <a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>.
            Source datasets retain their own licences.
          </p>
        </div>
        <nav aria-label="Footer">
          <Link to="/data/sources">Sources</Link>
          <Link to="/data/methodology">Methodology</Link>
          <Link to="/">Chargeworthy home</Link>
        </nav>
      </footer>
    </div>
  );
}
