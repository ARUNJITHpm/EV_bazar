import { lazy } from "react";
import * as content from "./content/Content";
import * as expansion from "./expansion/Expansion";
import { StateRegistrations as ServerStateRegistrations } from "./expansion/StateRegistrations";
import { DistrictDetails as ServerDistrictDetails } from "./districts/DistrictDetails";

// SSR renders the full document. Vite removes these eager server references
// from the browser build; Suspense hydrates the stored HTML as each route loads.
export const ContentIndex = import.meta.env.SSR
  ? content.ContentIndex
  : lazy(() => import("./content/Content").then((m) => ({ default: m.ContentIndex })));
export const ContentArticle = import.meta.env.SSR
  ? content.ContentArticle
  : lazy(() => import("./content/Content").then((m) => ({ default: m.ContentArticle })));
export const LatestWeekly = import.meta.env.SSR
  ? content.LatestWeekly
  : lazy(() => import("./content/Content").then((m) => ({ default: m.LatestWeekly })));
export const RecentInsights = import.meta.env.SSR
  ? content.RecentInsights
  : lazy(() => import("./content/Content").then((m) => ({ default: m.RecentInsights })));
export const TopicList = import.meta.env.SSR
  ? content.TopicList
  : lazy(() => import("./content/Content").then((m) => ({ default: m.TopicList })));
export const ElectricityContext = import.meta.env.SSR
  ? expansion.ElectricityContext
  : lazy(() => import("./expansion/Expansion").then((m) => ({ default: m.ElectricityContext })));
export const CorridorsContext = import.meta.env.SSR
  ? expansion.CorridorsContext
  : lazy(() => import("./expansion/Expansion").then((m) => ({ default: m.CorridorsContext })));
export const StateRegistrations = import.meta.env.SSR
  ? ServerStateRegistrations
  : lazy(() =>
      import("./expansion/StateRegistrations").then((m) => ({ default: m.StateRegistrations })),
    );
export const DistrictDetails = import.meta.env.SSR
  ? ServerDistrictDetails
  : lazy(() => import("./districts/DistrictDetails").then((m) => ({ default: m.DistrictDetails })));
