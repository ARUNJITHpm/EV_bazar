import { Methodology, Sources } from "./method/Method";
import {
  ContentIndex,
  ContentArticle,
  LatestWeekly,
  RecentInsights,
  TopicList,
  ElectricityContext,
  CorridorsContext,
  StateRegistrations,
  DistrictDetails,
} from "./route-components";
import { lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Link, Route, Routes, useLocation, useParams } from "react-router-dom";
import publicCatalogue from "virtual:analytics-public-data";
import atlas from "virtual:analytics-atlas";
import { DeferredDistrictMap } from "./districts/DeferredDistrictMap";
import { developmentFixtures } from "./data/client";
import { parseCsv } from "../../../scripts/csv";
import { datasetStructuredData } from "../../../scripts/analytics-seo";

import { analyticsMetadata, searchPublicContent, verticals } from "./catalog";

const ChartDemo = import.meta.env.DEV ? lazy(() => import("./chart/ChartDemo")) : null;
const MapDemo = import.meta.env.DEV ? lazy(() => import("./districts/MapDemo")) : null;

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
          : "Search published insights, weekly charts, topics and districts."}
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
        <LatestWeekly />
        <Link className="analytics-text-link" to="/data/weekly">
          Browse weekly charts <span aria-hidden="true">→</span>
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
        <RecentInsights />
        <Link className="analytics-text-link" to="/data/insights">
          Browse insights <span aria-hidden="true">→</span>
        </Link>
      </section>
      <Search districtsOnly />
      <Search />
      <TopicList />
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
  return (
    <DocumentPage title={district?.district_name ?? "District data"}>
      {district ? (
        <DistrictDetails district={district} />
      ) : (
        <>
          <Preparation>
            No district indicators have been published here yet. Search for a district in our
            archived reference.
          </Preparation>
          <Search districtsOnly />
        </>
      )}
    </DocumentPage>
  );
}

function InsightsPage() {
  return (
    <DocumentPage title="Insights">
      <ContentIndex format="insights" />
    </DocumentPage>
  );
}
function WeeklyPage() {
  return (
    <DocumentPage title="One question, one chart">
      <ContentIndex format="weekly" />
    </DocumentPage>
  );
}

function MethodologyPage() {
  return (
    <DocumentPage title="Methodology">
      <Methodology />
    </DocumentPage>
  );
}
function SourcesPage() {
  return (
    <DocumentPage title="Sources">
      <Sources />
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
  const { pathname, search, hash } = useLocation();
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
    if (window.location.hash) {
      const target = document.getElementById(decodeURIComponent(window.location.hash.slice(1)));
      target?.scrollIntoView?.();
    } else window.scrollTo(0, 0);
  }, [pathname, hash]);
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
    const origin = import.meta.env.PUBLIC_ANALYTICS_ORIGIN as string;
    let canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (origin) {
      if (!canonical) {
        canonical = document.createElement("link");
        canonical.rel = "canonical";
        document.head.append(canonical);
      }
      canonical.href = new URL(pathname, origin).href;
    }
    document.getElementById("analytics-datasets")?.remove();
    if (pathname.replace(/\/+$/, "") === "/data/sources") {
      const ld = document.createElement("script");
      ld.id = "analytics-datasets";
      ld.type = "application/ld+json";
      ld.textContent = JSON.stringify(datasetStructuredData(publicCatalogue));
      document.head.append(ld);
    }
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
      canonical?.remove();
      document.getElementById("analytics-datasets")?.remove();
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
        <Suspense fallback={<p role="status">Loading data page…</p>}>
          <Routes>
            {MapDemo && new URLSearchParams(search).get("fixtures") === "1" && (
              <Route
                path="map-demo"
                element={
                  <Suspense fallback={<p>Loading map…</p>}>
                    <MapDemo />
                  </Suspense>
                }
              />
            )}
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
                    {vertical.slug !== "corridors" && (
                      <Preparation>{vertical.preparation}</Preparation>
                    )}
                    {vertical.slug === "electricity" && <ElectricityContext />}
                    {vertical.slug === "corridors" && <CorridorsContext />}
                    {vertical.slug === "vehicles" && <StateRegistrations />}
                    {["vehicles", "charging-network", "usage"].includes(vertical.slug) && (
                      <DeferredDistrictMap
                        atlas={atlas}
                        districts={publicCatalogue.districts}
                        initialIndicator={
                          vertical.slug === "vehicles"
                            ? "registrations"
                            : vertical.slug === "usage"
                              ? "usage"
                              : "chargers"
                        }
                      />
                    )}
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
            <Route path="insights/:slug" element={<ContentArticle format="insights" />} />
            <Route path="weekly" element={<WeeklyPage />} />
            <Route path="weekly/:slug" element={<ContentArticle format="weekly" />} />
            <Route path="methodology" element={<MethodologyPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="*" element={<UnpublishedPage />} />
          </Routes>
        </Suspense>
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
