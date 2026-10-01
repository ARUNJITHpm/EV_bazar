# Methodology publication workflow

Part 7 renders `/data/methodology` and `/data/sources` as static documents, with JavaScript enhancement. Sources are generated from every validated public dataset metadata file; article chart usage is resolved from chart source URLs. Unacquired templates are listed as pending rather than treated as observations. Approved source metadata includes its own licence and attribution.

## Real validation summary

No real validation is approved today. The public page must say so; a synthetic unit test, demo run or private station report cannot replace it. Part 5 remains an unpublished working draft. Its model description is explicitly labelled as a draft, including its simulation limitations.

The build reads only `frontend/content/analytics/validation-summary.json` when present. This is the latest **reviewed public aggregate summary**, never the private report itself. The strict schema is in `frontend/src/features/analytics/method/reviewed.ts`. Unknown fields (including station IDs, raw LOO records and bill values), demos, missing version stamps and invalid metrics fail the build.

After reviewing a real completed run, prepare the aggregate summary with:

```powershell
python scripts/prepare_analytics_validation.py --report <private-report.json> --completed-on YYYY-MM-DD --approved
```

The script extracts LOO error, interval coverage, distinct station count, selected features, simulation count, validation outcome and six version stamps from the run report. It refuses demo and incomplete reports. `--approved` records the operator's review; it does not establish that inputs are real by itself. Do not invoke it on synthetic data. Confirm consent, units, full-month bills, physical inventory, held-out grouping, genuine inputs and missing/zero observation handling before approval. Keep the private report outside all public trees.

Commit the reviewed summary with the relevant publication. Each build displays those saved values automatically. A failed validation may be disclosed, but cannot authorize usage publication. Removing the summary returns the page to its pending state. No private file is emitted or bundled.

## Corrections

`frontend/content/analytics/corrections.json` starts empty. Add an entry only for an actual reviewed correction:

```json
[{"id":"stable-correction-slug","date":"YYYY-MM-DD","changed":"What changed","reason":"Why it changed","charts":["published-chart-id"]}]
```

IDs are unique and charts must exist in published articles. Dates must be calendar dates. The log sorts newest first. Every chart has a corrections-log link; affected charts link to the specific correction. Each log entry links back to its affected charts. Update the article's `updated_on` and changelog with the same correction, retain the source provenance, and check affected downloads. Extend the reviewed chart registry when non-article charts are published; do not bypass unknown-chart validation.

## CSV licences

Generated public CSVs start with one `# Chargeworthy Data: ` JSON comment naming original-content CC BY 4.0, source licence, source URL and attribution. Chart CSVs include the same comment and citations, licences and versions on every row. The shared CSV parser skips only this reserved preamble and keeps original line numbers in errors. External readers should skip this comment line before reading the column header. Source inputs are unchanged; catalogue checksums refer to the emitted download bytes. Metadata and README notes accompany source downloads. CC BY 4.0 does not relicense third-party data, including CC0 reference data or future ODbL highways.

## Ownership and revenue disclosure

The owner confirmed that Chargeworthy currently has no CPO affiliation, owns no
charging stations and does not plan to own them. The public disclosure reflects
those facts. The business model is based on site-assessment and operator-matching
fees. Fee timing is not stated: the owner's answer did not distinguish current
income from planned income. Do not claim either until confirmed.

This owner clarification supersedes the earlier CPO-affiliation statement in
OVERVIEW section 6.3 for the public analytics disclosure. The pre-existing local
OVERVIEW edits are preserved; no promise about future affiliations is implied.
