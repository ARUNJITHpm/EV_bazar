import { lazy, Suspense, type ReactNode } from "react";
import { createBrowserRouter } from "react-router-dom";

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
import { Landing } from "./features/landing/Landing";

/**
 * One SPA, two very different surfaces.
 *
 *   /            public - the report is a document, styled as an instrument
 *                panel (STACK.md §7)
 *   /console/*   internal - an ordinary admin tool, behind auth
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

function Deferred({ children }: { children: ReactNode }) {
  return (
    <Suspense fallback={<p className="font-data text-[13px] text-ink-faint">…</p>}>
      {children}
    </Suspense>
  );
}

export const router = createBrowserRouter([
  { path: "/", element: <Landing /> },
  {
    path: "/console",
    element: <ConsoleLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "progress", element: <Progress /> },
      { path: "lookup", element: <Lookup /> },
      { path: "cpo", element: <Cpo /> },
      { path: "competitors", element: <Competitors /> },
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
