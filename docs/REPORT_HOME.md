# Report as homepage

The homepage renders the stored flagged demonstration report `KL-TVM-DEMO-001`
with the twelve-section paper renderer. It never runs a new prediction or ROI
calculation. The existing landing page is at `/about`.

| Route | Behaviour |
| --- | --- |
| `/` | Stored demonstration report, navigation, retry and print controls |
| `/about` | Existing landing page, with corrected business disclosures |
| `/report/sample` | Redirect to the stored demonstration report |
| `/report/:id` | Stored customer or demo report, returned verbatim |
| `/report/sample/:which` | Explicitly fictional build/conditional/rejection review fixtures |
| `/assess`, `/assess/:step` | Existing assessment flow |
| `/data/*` | Existing public analytics |
| `/owner/*` | Existing station-owner flow |
| `/console/*` | Existing operations console with server-side session authorization |
| Unmatched routes | Page-not-found screen with a homepage link |

The report schema accepts a null operator IRR. An undefined IRR is preserved as
null, rather than converted to a zero return. Optional fields added for the newer
renderer do not rewrite older reports. The frontend reads through the generated
OpenAPI client. Stored JSON and archived PDF bytes are unchanged by viewing or
printing; the browser's print control produces a copy of the current presentation.

Chargeworthy has no current CPO affiliation, owns or operates no charging
stations, and earns assessment and operator-matching fees. Demonstration operator
arrangements are illustrative. Unverified assessment counts and rejection rates
are not presented as a track record. The deposit comparison is explicitly an
illustrative assumption, not a current bank offer. Report viewing makes no paid
imagery calls.

`scripts/check_report_home.py` exercises 390px and 1440px homepages, all twelve
sections, nullable operator IRRs, navigation, direct-route refresh, accessibility
and PDF output. It intercepts only report reads with an existing flagged fixture;
it never generates predictions or writes to a database. Frontend CI runs this
check after every build using the locked Playwright Chromium revision.

Run locally after `npm run build --prefix frontend`:

```powershell
uv run playwright install chromium
uv run python scripts/check_report_home.py
```
