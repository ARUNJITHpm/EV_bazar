import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter } from "react-router-dom";
import { AnalyticsApp } from "./features/analytics/AnalyticsApp";

const Concept = lazy(() =>
  import("./features/console/Concept").then((m) => ({ default: m.Concept })),
);
const ConsoleLayout = lazy(() =>
  import("./features/console/ConsoleLayout").then((m) => ({ default: m.ConsoleLayout })),
);
const Competitors = lazy(() =>
  import("./features/console/Competitors").then((m) => ({ default: m.Competitors })),
);
const Cpo = lazy(() => import("./features/console/Cpo").then((m) => ({ default: m.Cpo })));
const Data = lazy(() => import("./features/console/Data").then((m) => ({ default: m.Data })));
const Lookup = lazy(() => import("./features/console/Lookup").then((m) => ({ default: m.Lookup })));
const Network = lazy(() =>
  import("./features/console/Network").then((m) => ({ default: m.Network })),
);
const Overview = lazy(() =>
  import("./features/console/Overview").then((m) => ({ default: m.Overview })),
);
const Progress = lazy(() =>
  import("./features/console/Progress").then((m) => ({ default: m.Progress })),
);
const Reports = lazy(() =>
  import("./features/console/Reports").then((m) => ({ default: m.Reports })),
);
const SpendLlm = lazy(() =>
  import("./features/console/SpendLlm").then((m) => ({ default: m.SpendLlm })),
);
const SpendMaps = lazy(() =>
  import("./features/console/SpendMaps").then((m) => ({ default: m.SpendMaps })),
);
const Vahan = lazy(() => import("./features/console/Vahan").then((m) => ({ default: m.Vahan })));
const Landing = lazy(() =>
  import("./features/public/Landing").then((m) => ({ default: m.Landing })),
);
const ReportRoute = lazy(() =>
  import("./features/report/ReportRoute").then((m) => ({ default: m.ReportRoute })),
);

/**
 * One SPA, three surfaces.
 *
 *   /            public - Chargeworthy: the landing and the assessment
 *                flow, on the dark brand ground (design/)
 *   /report/:id  the document, on paper - a stored payload served verbatim
 *   /animation   a review surface for candidate hero animations - unlinked
 *                and carrying no real data (features/animation/)
 *   /console/*   internal - an ordinary admin tool, behind auth, keeping
 *                the instrument-panel palette
 *
 * The console routes are guarded on the SERVER, by require_operator on every
 * console_* endpoint. A hidden React route is not access control (PLAN C.0).
 */

/**
 * Split out because it pulls in Leaflet (~160 kB), and the public report must
 * not carry a mapping library so that one operator can place pins. Lazy here
 * is a payload decision, not a code-organisation one.
 */
const Geocoding = lazy(() =>
  import("./features/console/Geocoding").then((m) => ({ default: m.Geocoding })),
);

/** Same payload decision: the flow carries the pin-drop map (Leaflet). */
const Flow = lazy(() => import("./features/public/flow/Flow").then((m) => ({ default: m.Flow })));

/**
 * The motion workbench. Lazy for the same reason: nobody arriving at the
 * landing page should pay to download three candidate hero animations they
 * are not going to see.
 */
const Animations = lazy(() =>
  import("./features/animation/Animations").then((m) => ({ default: m.Animations })),
);

/** Station-owner upload: its own route, its own chunk. */
const Owner = lazy(() => import("./features/owner/Owner").then((m) => ({ default: m.Owner })));
const OwnerHome = lazy(() =>
  import("./features/owner/Home").then((m) => ({ default: m.OwnerHome })),
);
const StationPage = lazy(() =>
  import("./features/owner/Home").then((m) => ({ default: m.StationPage })),
);
const BillPage = lazy(() => import("./features/owner/Home").then((m) => ({ default: m.BillPage })));

function Deferred({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="min-h-dvh bg-cw-ground" />}>{children}</Suspense>;
}

const flow = (
  <Deferred>
    <Flow />
  </Deferred>
);

export const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <Deferred>
        <Landing />
      </Deferred>
    ),
  },
  { path: "/data/*", element: <AnalyticsApp /> },
  /**
   * Every step is a real URL, which is what makes the browser back button
   * work through the flow without a history shim.
   */
  { path: "/assess", element: flow },
  { path: "/assess/:step", element: flow },
  /**
   * Station-owner upload (api/internal/owner.py). Open, like /assess: an
   * owner holds no login. Every step is a URL; answers live in sessionStorage.
   */
  {
    path: "/owner",
    element: (
      <Deferred>
        <Owner />
      </Deferred>
    ),
  },
  {
    path: "/owner/home",
    element: (
      <Deferred>
        <OwnerHome />
      </Deferred>
    ),
  },
  {
    path: "/owner/station/:id",
    element: (
      <Deferred>
        <StationPage />
      </Deferred>
    ),
  },
  {
    path: "/owner/station/:id/bill",
    element: (
      <Deferred>
        <BillPage />
      </Deferred>
    ),
  },
  {
    path: "/owner/:step",
    element: (
      <Deferred>
        <Owner />
      </Deferred>
    ),
  },

  /**
   * The stored JSONB payload, fetched by id and rendered verbatim (AGENTS.md
   * rule 9). The demo report is /report/KL-TVM-DEMO-001; customer ids are
   * UUID strings.
   */
  {
    path: "/report/:id",
    element: (
      <Deferred>
        <ReportRoute />
      </Deferred>
    ),
  },
  /**
   * Unlinked on purpose - a review surface, not a page. Nothing on it is
   * real data; see features/animation/data.ts.
   */
  {
    path: "/animation",
    element: (
      <Deferred>
        <Animations />
      </Deferred>
    ),
  },
  {
    path: "/console",
    element: (
      <Deferred>
        <ConsoleLayout />
      </Deferred>
    ),
    children: [
      { index: true, element: <Overview /> },
      { path: "concept", element: <Concept /> },
      { path: "progress", element: <Progress /> },
      { path: "lookup", element: <Lookup /> },
      { path: "cpo", element: <Cpo /> },
      { path: "network", element: <Network /> },
      { path: "competitors", element: <Competitors /> },
      { path: "vahan", element: <Vahan /> },
      { path: "data", element: <Data /> },
      {
        path: "geocoding",
        element: (
          <Deferred>
            <Geocoding />
          </Deferred>
        ),
      },
      { path: "spend/maps", element: <SpendMaps /> },
      { path: "spend/llm", element: <SpendLlm /> },
      { path: "reports", element: <Reports /> },
    ],
  },
]);
