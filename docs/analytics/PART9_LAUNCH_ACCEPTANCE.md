# Part 9 launch acceptance checkpoint

Implemented 2026-10-02. Public build acceptance is repeatable; this is not a claim
that the production site or a physical Android has passed launch acceptance.
Parts 12/13 source-dependent work remains deferred as requested.

## What changed

Public Data documents use local licensed fonts compressed as full-font WOFF2 (no subset) and paint before SPA enhancement.
The shell hydrates prerendered HTML; content, charts, reports and console routes
load separately. Pages without charts do not request chart JavaScript. Map code
and validated TopoJSON load only when their section is visible, with retry on a
failed boundary request. No private API is involved in public prerendering.

Every one of the 797 generated documents has a distinct title and description.
The seven currently indexable routes form the publication allowlist; empty
districts and preparation verticals remain noindex. Sources carries Dataset
JSON-LD for both downloadable datasets with their own licences and source URLs.
Sitemap and canonical links require PUBLIC_ANALYTICS_ORIGIN; an absent setting
emits neither, rather than inventing a domain. SPA navigation updates/removes
canonical and Dataset tags as appropriate.

The build scan checks all artifacts, including binary files and source maps,
for canaries and supplied private string identifiers. Public payloads additionally
reject owner identity, bill and grid fields. Shared owner form code is allowed in
the single SPA; private values are checked everywhere. Short numeric identifiers
are protected by public field gates; the string comparison is not a generic PII
classifier or OCR scan. The local read-only database snapshot has zero owner
accounts, stations and bill images. This cannot prove a populated production
store comparison. Snapshot files stay in local_scratch, outside git/build output.

Docker's four existing image tags now carry verified registry manifest digests.
uv.lock fixes Playwright and therefore its Chromium revision. The origin is wired
as a Docker build argument and a GitHub Actions repository variable. Container
execution has not been tested here because Docker is unavailable.

## Verification

- Frontend: all 178 tests across 22 files passed. New tests cover privacy refusal,
  Dataset metadata/licences, sitemap origin validation and viewport/null/retry.
- Backend: all 713 tests passed using the existing isolated osmium 4.2.0 tools.
  Without that optional acquisition environment the OSM extraction module skips.
- Strict production build/typecheck passed; 797 public documents were prerendered.
- Axe 4.11.0: zero violations on Data, Electricity, district, insight, weekly and
  Sources pages at 390px and 1440px. No horizontal overflow or page errors.
- Every rendered article chart has source/date, a working table, and both real
  CSV downloads. Licensed/checksummed source downloads and correction anchors
  passed. Header/home Data links, keyboard skip link, no-JS article tables,
  district suppression and production fixture exclusion passed.
- Public build gates refused malformed rows in the reference and all five
  expansion datasets. All 907 built artifacts passed the private-field/canary
  scan, including a comparison with the empty local private-store snapshot.
- The existing labelled stored demo report renders through its lazy route and
  the PDF-ready marker. Playwright produced a PDF without rerunning a model or
  changing persisted payloads/archived artifacts. The CI template exercises this path once activated.
- Upstream OFL licence files are retained byte-for-byte, including their two
  original trailing spaces; the code whitespace check excludes only those licences.
- Scoped new TypeScript lint and Python Ruff passed. The older repository-wide
  ESLint configuration is still absent; this is not a claim of a full lint pass.
- Performance receipt: /data: FCP 1.112?1.212s (median 1.156s); LCP 1.112?1.212s; /data/district/ernakulam-555: FCP 0.824?0.864s (median 0.848s); LCP 0.824?0.864s. All six foreground runs passed the under-2s FCP lab gate; this is not physical Android/deployed-host or full-interactivity acceptance..

Evidence: local_scratch/part9_acceptance/ (baseline, acceptance JSON, PDF,
read-only private snapshot); .impeccable/review/part9/ (desktop/mobile captures).
These are local evidence, not public datasets. Browser measurements use cold
cache, 4x CPU slowdown, 9 Mbps download, 1.5 Mbps upload and 150 ms latency.
FCP is readable prerendered content, not full interactivity; LCP is recorded
separately. Repeat on the actual deployed URL and a mid-range Android over 4G.

## Re-run and finish launch acceptance

GitHub rejected the workflow push because the connected OAuth app has repo
but no workflow scope. The complete job is saved at
[ci/analytics-acceptance.yml](ci/analytics-acceptance.yml). After enabling workflow
scope, install that file as .github/workflows/analytics-acceptance.yml (omit the
first template comment if preferred). No workflow is active from this checkpoint.


1. Set the verified HTTPS origin in the build shell/.env.local and the deployed
   Docker build argument. For Actions use repository variable
   PUBLIC_ANALYTICS_ORIGIN. Build and confirm sitemap/canonical URLs on the host.
2. Run npm run build and npm run data:check-build from frontend, sequentially.
3. Run python scripts/check_analytics_launch.py --url <preview-or-host>
   --report-payload tests/fixtures/part9-stored-report.json --output <private-path>/acceptance.json.
   Use the locked project Python/Chromium and pinned frontend axe-core.
   --skip-performance is for functional CI only, not a performance pass.
4. Privately obtain an authorised read-only owner identity snapshot containing
   station/account identifiers, names, addresses, phones and file keys. Do not
   put it in data/public or frontend. Run node scripts/check-owner-grid-public.ts
   dist <private-snapshot.json> from frontend; failures never print record values.
   Compare populated production records, including grid revisions, before launch.
5. Confirm deployed no-JS/nested paths, actual Android/4G performance, mobile
   controls, sitemap and WhatsApp link previews; install the CI template and verify its job is green.
   Docker build/run remains required before describing container acceptance as done.
6. Acquire and review deferred source datasets before enabling more indicators,
   district indexing or promotion. Public references and empty states can ship;
   source-dependent marketing claims cannot be inferred from these checks.

Rollback: revert this scoped Part 9 commit and rebuild. No migration, private
store mutation, prediction or persisted-report rewrite is part of this change.

## Files created or changed

| File | Purpose |
| --- | --- |
| `docs/analytics/ci/analytics-acceptance.yml` | Reviewable browser/SEO/PDF CI template; activation requires workflow scope. |
| `Dockerfile` | Pin image digests; wire public origin. |
| `chargeworthy-data-roadmap.md` | Checkpoint status, evidence and remaining launch requirements. |
| `docs/analytics/PART9_IMAGE_DIGESTS.json` | Record verified public registry manifest URLs/digests. |
| `docs/analytics/PART9_LAUNCH_ACCEPTANCE.md` | Checkpoint status, evidence and remaining launch requirements. |
| `docs/analytics/SPEC.md` | Checkpoint status, evidence and remaining launch requirements. |
| `frontend/.env.example` | Expose the explicit public origin build setting. |
| `frontend/package-lock.json` | Checkpoint status, evidence and remaining launch requirements. |
| `frontend/package.json` | Checkpoint status, evidence and remaining launch requirements. |
| `frontend/public/analytics-fonts/IBMPlexMono-OFL.txt` | Self-host existing fonts, OFL licences and hash provenance. |
| `frontend/public/analytics-fonts/IBMPlexMono.ttf` | Self-host existing fonts, OFL licences and hash provenance. |
| `frontend/public/analytics-fonts/SourceSerif4-OFL.txt` | Self-host existing fonts, OFL licences and hash provenance. |
| `frontend/public/analytics-fonts/SourceSerif4.ttf` | Self-host existing fonts, OFL licences and hash provenance. |
| `frontend/public/analytics-fonts/provenance.json` | Self-host existing fonts, OFL licences and hash provenance. |
| `frontend/scripts/analytics-seo.test.ts` | Dataset/sitemap helpers and metadata tests. |
| `frontend/scripts/analytics-seo.ts` | Dataset/sitemap helpers and metadata tests. |
| `frontend/scripts/atlas.ts` | Keep validated geometry separate from route JavaScript. |
| `frontend/scripts/check-owner-grid-public.ts` | All-artifact identifier/field privacy scan and refusal tests. |
| `frontend/scripts/prerender-analytics.mjs` | Prerender bootstrap, local font links, publication list and SEO output. |
| `frontend/scripts/private-build.test.ts` | All-artifact identifier/field privacy scan and refusal tests. |
| `frontend/scripts/private-build.ts` | All-artifact identifier/field privacy scan and refusal tests. |
| `frontend/scripts/public-data-plugin.ts` | Keep validated geometry separate from route JavaScript. |
| `frontend/src/features/analytics/AnalyticsApp.test.tsx` | Update component checks for progressive loading; browser checks cover real chunks. |
| `frontend/src/features/analytics/AnalyticsApp.tsx` | Route boundaries, deferred map and navigation-correct metadata. |
| `frontend/src/features/analytics/catalog.ts` | Unique document titles and descriptions with explicit LGD identity. |
| `frontend/src/features/analytics/chart/Plot.tsx` | Distinct chart-region accessibility names. |
| `frontend/src/features/analytics/chart/ProgressiveChart.tsx` | Request chart code only when an actual chart renders. |
| `frontend/src/features/analytics/chart/model.ts` | Checkpoint status, evidence and remaining launch requirements. |
| `frontend/src/features/analytics/content/Content.test.tsx` | Update component checks for progressive loading; browser checks cover real chunks. |
| `frontend/src/features/analytics/content/Content.tsx` | Use deferred charts or unchanged light stamps. |
| `frontend/src/features/analytics/data/client.ts` | Load CSV validators only when a CSV is requested. |
| `frontend/src/features/analytics/data/schemas.ts` | Keep unchanged six stamps separate from validators. |
| `frontend/src/features/analytics/data/versions.ts` | Keep unchanged six stamps separate from validators. |
| `frontend/src/features/analytics/districts/DeferredDistrictMap.tsx` | Load map/geometry in view; null/error/retry handling and tests. |
| `frontend/src/features/analytics/districts/DistrictDetails.tsx` | Valid definition lists, deferred locator and chart imports. |
| `frontend/src/features/analytics/districts/viewport-atlas.test.tsx` | Load map/geometry in view; null/error/retry handling and tests. |
| `frontend/src/features/analytics/districts/viewport-atlas.ts` | Keep validated geometry separate from route JavaScript. |
| `frontend/src/features/analytics/expansion/Expansion.tsx` | Use deferred charts or unchanged light stamps. |
| `frontend/src/features/analytics/expansion/StateRegistrations.tsx` | Use deferred charts or unchanged light stamps. |
| `frontend/src/features/analytics/expansion/model.ts` | Use deferred charts or unchanged light stamps. |
| `frontend/src/features/analytics/route-components.tsx` | Lazy browser routes with complete server documents. |
| `frontend/src/features/public/flow/district-context.ts` | Read identical stamps from the light module. |
| `frontend/src/routes.tsx` | Lazy browser routes with complete server documents. |
| `frontend/src/styles/analytics.css` | Scope local font families to Data documents. |
| `frontend/vite.config.ts` | Expose the explicit public origin build setting. |
| `scripts/check_analytics_launch.py` | Foreground lab metrics, axe, controls, no-JS, SEO and stored-report PDF checks. |
| `tests/fixtures/part9-stored-report.json` | Existing persisted demo payload for offline PDF acceptance; no model run. |
| `frontend/public/analytics-fonts/IBMPlexMono.woff2` | Full-font WOFF2 encoding or conversion hash/tool provenance; OFL retained. |
| `frontend/public/analytics-fonts/SourceSerif4.woff2` | Full-font WOFF2 encoding or conversion hash/tool provenance; OFL retained. |
| `frontend/public/analytics-fonts/woff2-provenance.json` | Full-font WOFF2 encoding or conversion hash/tool provenance; OFL retained. |
