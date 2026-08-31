import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter } from "react-router-dom";

import { Concept } from "./features/console/Concept";
import { ConsoleLayout } from "./features/console/ConsoleLayout";
import { Competitors } from "./features/console/Competitors";
import { Cpo } from "./features/console/Cpo";
import { Data } from "./features/console/Data";
import { Lookup } from "./features/console/Lookup";
import { Overview } from "./features/console/Overview";
import { Progress } from "./features/console/Progress";
import { Reports } from "./features/console/Reports";
import { SpendLlm } from "./features/console/SpendLlm";
import { SpendMaps } from "./features/console/SpendMaps";
import { Vahan } from "./features/console/Vahan";
import { Landing } from "./features/public/Landing";
import { ReportRoute } from "./features/report/ReportRoute";

/**
 * One SPA, three surfaces.
 *
 *   /            public - Chargeworthy: the landing and the assessment
 *                flow, on the dark brand ground (design/)
 *   /report/:id  the document, on paper - a stored payload served verbatim
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

function Deferred({ children }: { children: ReactNode }) {
  return <Suspense fallback={<div className="min-h-dvh bg-cw-ground" />}>{children}</Suspense>;
}

const flow = (
  <Deferred>
    <Flow />
  </Deferred>
);

export const router = createBrowserRouter([
  { path: "/", element: <Landing /> },
  /**
   * Every step is a real URL, which is what makes the browser back button
   * work through the flow without a history shim.
   */
  { path: "/assess", element: flow },
  { path: "/assess/:step", element: flow },
  /**
   * The stored JSONB payload, fetched by id and rendered verbatim (AGENTS.md
   * rule 9). The demo report is /report/KL-TVM-DEMO-001; customer ids are
   * UUID strings.
   */
  { path: "/report/:id", element: <ReportRoute /> },
  {
    path: "/console",
    element: <ConsoleLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "concept", element: <Concept /> },
      { path: "progress", element: <Progress /> },
      { path: "lookup", element: <Lookup /> },
      { path: "cpo", element: <Cpo /> },
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
