# Shared public reference data

Part 12 implementation: five expansion schemas, pending templates, development
fixtures, production validation and read-only backend lookup. **OSM power is
available: 7,726 regional mapped observations; district joins unresolved.**
The other four expansion datasets remain pending. See the acquisition evidence
and owner actions in [PART12_SOURCE_REVIEW.md](PART12_SOURCE_REVIEW.md). Source gates remain in
[DATA_SOURCES_TODO.md](DATA_SOURCES_TODO.md). Toll traffic stays conditional and
is not registered until an acceptable licensed count is found.

## One validation path

`frontend/src/features/analytics/data/schemas.ts` owns the allowlisted schemas.
`frontend/scripts/public-data.ts` validates files, metadata, natural keys and
reference joins before publishing anything. The same loader powers browser
assets and the offline backend export. Adding a source does not require another
parser or independently acquired backend copy.

Each expansion directory contains `data.template.csv` and
`meta.template.json`; reviewed OSM observations also have active `data.csv` and
`meta.json`. Complete
source checksum, licence URL, review reference and transformation version before
activation. The review reference identifies a review record, not private owner
data. The checksum identifies the upstream artifact; raw CSV and metadata
digests are separately computed during validation.

The five schemas add these provenance refinements to the roadmap fields:

- DISCOM: stable `discom_id`, `metric_basis`, fiscal-year checks and signed
  integer paise for the gap. Edition participates in the natural key; acquisition
  review must select compatible canonical observations rather than treating
  restated years as extra independent observations.
- Supply: paired nullable utility ID/name, actual full reporting interval,
  rural/urban/all scope and `supply_definition`. Other intervals are permitted
  explicitly; monthly or annual intervals must match their declared calendar.
- Policies: notification plus clause, eligibility, nullable supersession and
  validity. Amount text stays text. No benefit is automatically approved.
- WSA: paired nullable coordinates, nullable printed document date, dated status
  evidence and explicit true/false/unknown charging flag. Status remains as printed.
- OSM power: typed OSM object ID, node/representative-point derivation, nullable
  voltage and unresolved LGD join. Licence and attribution retain ODbL.

Geography joins use the dated district reference. A missing district code stays
unknown; a present code must exist and agree with any declared state. State
observations never become district measurements. All observations carry the
six public version stamps; the expanded schema version is `public_analytics_v2`.

## Offline export and backend use

After acquiring and reviewing sources, run from the repository root:

```powershell
node frontend/scripts/export-public-reference.ts data/public local_scratch/public-reference.json
```

The command refuses fixture sources, validates through the same loader and
prints the SHA256 of its normalized snapshot. It writes outside `data/public`.
Deploy the snapshot with the exact validated public source tree, and pin the
printed digest in the release configuration. Regenerate after any CSV,
metadata, activation or schema change. Generate after checkout so platform line
endings are included in the actual source digests.

Backend callers use `app.domain.public_reference.PublicReference.load` with
explicit snapshot path, public source root and expected release SHA256. Loading
refuses fixture snapshots, unsupported stamps, source/metadata changes, newly
activated sources absent from the snapshot and paths escaping the source tree.
The release digest is the validation trust boundary: approve the output of the
offline validator, never construct or edit a snapshot by hand. No Node process,
HTTP request or SQL runs during lookup.

`lookup(dataset, state=..., lgd_code=..., discom_id=...)` returns status,
immutable-by-copy rows, source metadata, all six stamps and snapshot digest.
Statuses distinguish `pending`, `available` and `no_matching_observations`.
An absent dataset produces no invented values. District lookup returns exact
district observations plus wider state/utility context at its original scope;
it does not add a district code to area-average rows. Unresolved OSM geography
cannot be assigned a state through a guess. A utility filter is an explicit
identifier filter, never an inferred site/provider match. Policy lookups return
dated history, including central context; report consumers must check validity
and eligibility rather than interpreting presence as an entitlement.

Parts 13 and 14 will call these lookups from domain code, using reviewed
jurisdiction evidence to identify serving utilities. Nearest-equipment and
route distances require the geography queries specified in AGENTS.md; this
module does not approximate distances with planar or straight-line calculations.
No report payload, archived PDF, API contract, economics rule or database is
modified in Part 12.

## Subsidy comparison

`scripts/compare_public_policies.py` takes the approved snapshot, pinned digest
and an explicit JSON array exported from `subsidy_rules`. It never connects to
the database. It reports unmatched source URLs and source-match candidates,
date/eligibility differences and complete review context. A shared URL is only
a candidate: clauses, state codes, charger classes and monetary terms require
human review. It does not parse `amount_text`, perform fuzzy matching, modify
either input, or apply a subsidy. A pending policy dataset refuses comparison.

```powershell
.venv/Scripts/python.exe -m scripts.compare_public_policies --snapshot local_scratch/public-reference.json --public-root data/public --sha256 RELEASE_DIGEST --subsidy-rules-json local_scratch/subsidy_rules.json
```

## Acceptance

- `npm run test --prefix frontend`: schema, parser, fixture and frontend tests.
- `npm run build --prefix frontend`: actual validation, TypeScript and public build.
- `npm run data:check-build --prefix frontend`: actual build refusal for the
  district reference and each expansion dataset, followed by fixture scanning.
  Run with no concurrent builds; temporary broken inputs are restored in finally.
- `python -m pytest tests/test_public_reference.py`: backend lookups, null
  handling, pins, freshness, source containment and read-only comparison.
- Scoped Ruff, strict mypy and Prettier checks.

Passing fixture checks proves implementation, not live acquisition or source
coverage. Reports must retain pending/unverified states until real reviewed
inputs pass the same validator. Acquisition remains necessary before calling
the whole Part 12 live-data delivery complete.
