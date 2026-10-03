import { renderToString } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { AnalyticsApp } from "./AnalyticsApp";
export { analyticsMetadata, staticAnalyticsPaths } from "./catalog";

export function renderAnalytics(path: string): string {
  return renderToString(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/data/*" element={<AnalyticsApp />} />
      </Routes>
    </MemoryRouter>,
  );
}

export {
  socialSvg,
  socialFormats,
  socialImagePath,
  assertSocialSvgLegibility,
} from "./chart/social";
export { pngWithProvenance } from "./chart/social-png";
export { default as socialArticles } from "virtual:analytics-content";
