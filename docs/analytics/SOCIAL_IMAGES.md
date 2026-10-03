# Social image exports

Part 8 uses one pure SVG template for all three PNG formats. Node and
`@resvg/resvg-js` run only during the build; Caddy serves static PNGs. Browser
exports load the same template on demand and rasterise it with canvas.

## Public origin and launch check

Set `VITE_ANALYTICS_SITE_ORIGIN` to the actual public HTTPS origin, without a
trailing slash or path, before building for deployment. It becomes the page URL
in generated images and the absolute `og:image` URL in weekly documents. It
must also be passed to the frontend Docker build environment when deploying
through Docker; existing Docker deployment configuration is unchanged.

Until that origin is confirmed, builds produce clearly labelled localhost
preview images and relative OG image metadata. These are development review
artifacts, not evidence that deployed WhatsApp previews work. After deploying
with the configured origin, open a weekly URL in WhatsApp and confirm that its
question and 1200 x 630 image appear. This needs an accessible deployed page;
local browser checks cannot complete that acceptance item.

## Template and data fidelity

The template accepts only validated public chart rows, preserves missing values
and labelled P10/P50/P90 intervals, and exports the current displayed selection.
It uses horizontal comparisons so categories and intervals fit at a readable
size; lines connect adjacent available points within a series. Suppressed or
missing rows are never converted to zero. The prominent number is the largest
available value in the selection, labelled with its category and unit; for a
single-row chart its unit appears beneath the number. Estimates label P50 and
include P10 and P90. A missing selection has no numerical headline.

The reviewed content adapter supplies a question and short historical context.
Current weekly images count 783 entries in the archived district reference;
2024 coverage is explicit. These do not describe current districts or EV activity.

Each image includes the question, graph, prominent number, source names and
licences, wordmark and page URL. Full source URLs, attribution, update date,
original-content CC BY 4.0 licence, selected rows and all six version stamps
are embedded as PNG UTF-8 iTXt metadata. The original chart renderer stamp is
retained alongside `analytics_social_v1`. Source data retains its own licence.

Colours resolve from the report's CSS tokens. Source Serif 4 and IBM Plex Mono
are vendored from the pinned Google Fonts revision in
`frontend/public/analytics-fonts/provenance.json`, with checksums and both SIL
OFL licences. Builds verify those bytes and disable system-font loading.
Browser downloads embed those same fonts; they do not depend on Google Fonts
being reachable. No paid API or production Node process is involved.

## Legibility gates and outputs

- Portrait: 1080 x 1350; minimum text 36px; at most six comparison rows.
- Square: 1080 x 1080; minimum text 36px; at most three rows, further limited by
  available row height.
- Open Graph: 1200 x 630; minimum text 40px; one comparison row, further limited
  by available row height and label width.

These minima remain at least 10px when the image is displayed 300px wide.
Titles and headline figures are larger. Wrapping never shrinks text; overflowing
labels, sources, URLs or dense selections fail with a readable error. The build
also refuses weekly posts that cannot fit all their data in each format. Choose
a larger format, filter the chart, or edit reviewed wording to fit; never shorten
source information by silently clipping it. Browser errors leave Save image
available to retry.

Each weekly post gets three PNGs and matching public SVG audit artifacts at
`/analytics-images/<slug>-<format>.*`. `manifest.json` records dimensions,
checksums and whether a public origin was configured. Unknown/unpublished
posts receive no image. The build reads only the reviewed public content tree.

Run the production build and frontend tests, then run:

```powershell
.venv/Scripts/python scripts/check_analytics_social.py --url http://127.0.0.1:4195
```

The browser check verifies every weekly PNG checksum, dimensions and iTXt
provenance; measures SVG glyph bounds using the pinned fonts; downloads all
formats through the UI; checks no-data disabling, mobile overflow and OG tags
with JavaScript on and off; and saves a 300px-wide gallery for visual review.
The privacy build scan and existing article browser checks remain required.
