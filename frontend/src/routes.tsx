import { createBrowserRouter } from "react-router-dom";

import { ConsoleLayout } from "./features/console/ConsoleLayout";
import { Cpo } from "./features/console/Cpo";
import { Data } from "./features/console/Data";
import { Geocoding } from "./features/console/Geocoding";
import { Overview } from "./features/console/Overview";
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
export const router = createBrowserRouter([
  { path: "/", element: <Landing /> },
  {
    path: "/console",
    element: <ConsoleLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "cpo", element: <Cpo /> },
      { path: "data", element: <Data /> },
      { path: "geocoding", element: <Geocoding /> },
      { path: "spend/maps", element: <SpendMaps /> },
      { path: "spend/llm", element: <SpendLlm /> },
      { path: "reports", element: <Reports /> },
    ],
  },
]);
