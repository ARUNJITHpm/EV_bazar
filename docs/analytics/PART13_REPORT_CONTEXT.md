# Part 13 report context checkpoint

Implemented 2026-10-01 using the reviewed Part 12 OSM power source. **This is
the available-source checkpoint, not completion of every Part 13 source check.**
The remaining Parts 12 and 13 work is deliberately deferred at the owner's request.

## Available behavior

- A newly assembled report can use the same validated, release-pinned public
  reference snapshot as Part 12. No separate source import or runtime Node.
- PostGIS `ST_DWithin` / `ST_Distance` on EPSG:4326 geography selects the nearest
  mapped transformer within 2 km; only if none exists there does it select a
  mapped substation. Stable object ID resolves distance ties.
- Null LGD codes stay null. Point proximity does not assign a state, district
  or serving utility. Way distance is to its first mapped perimeter vertex,
  not a surveyed equipment centre. Raw voltage tags are explicitly unverified.
- Missing observations say “none mapped nearby within 2 km in this regional
  extract; coverage incomplete”. An absent source says “not assessed”. Neither
  statement establishes that real equipment is absent.
- The transformer-distance check remains unverified and neutral. Written
  DISCOM confirmation of spare capacity at the existing engine's advised
  managed-peak kVA appears as a stored checkable condition. Mapping changes
  no capex, load recommendation, demand feature, subsidy, verdict or ROI input.
- Every unverified emitted fact appears in the ledger. Pending DISCOM and
  district EV/charger checks are explicit, never fabricated zeros.
- Optional `public_context` carries source status, source URL/checksum,
  reporting/retrieval dates, transformation version and licence. Provenance
  retains all six report stamps, adds the snapshot digest and ODbL attribution,
  and stamps enriched reports `0013_public_context_v1`.
- Reports with no configured reference retain their existing checks and
  provenance. Old stored JSON validates and is returned without adding default
  fields. The read route never enriches reports or regenerates archived PDFs.

## Release configuration

Export through the shared validator after checkout (see PUBLIC_REFERENCE.md):

```powershell
node frontend/scripts/export-public-reference.ts data/public local_scratch/public-reference.json
```

Configure all three together for the backend process:

- `REPORT_PUBLIC_REFERENCE_SNAPSHOT`: exported snapshot file path.
- `REPORT_PUBLIC_REFERENCE_ROOT`: the exact validated `data/public` tree.
- `REPORT_PUBLIC_REFERENCE_SHA256`: digest printed by that export.

No settings means no enrichment. Partial or invalid settings fail closed.
The reference is immutable and cached by release identity; restart after source
or release changes. Do not edit snapshots manually. This checkpoint does not
configure or deploy production, regenerate old reports or write to a database.
Callers/tests may inject a validated `PublicReference` into `assemble_report`.

## Compatibility with unpublished report work

The current workspace has a twelve-section report rebuild that is not on
`origin/main`. Part 13 does not publish that rebuild or its unrelated changes.
The local twelve-section report prints the grid condition in section 08.
The published seven-section report prints it within the verdict section through
the same `GridConditions` component. Move that published placement to section
08 when the report rebuild is separately reviewed and published.

`coverage.py` exposes `public_context_gaps` for raw stored payloads. The local
twelve-section console also includes pending context in its provenance gaps;
its old per-section coverage remains unpublished. The dedicated public checker
reports old payloads lacking context without validating/default-filling them.

The synthetic JSON under report fixtures contains only public context for UI
tests; it is not a live source or an assessment. Restricted source archives
and human policy proposals remain outside public build output.

## Deferred work to resume later

| Part | Remaining work | Gate before implementation/activation |
| --- | --- | --- |
| 12 | PFC DISCOM observations | Written commercial reuse permission, human-checked tables/metric basis, canonical edition, stable utility identities and reviewed serving jurisdictions. Permission-request draft is prepared; nothing sent. |
| 12 | CEA/NPP supply observations | Confirm hour representation/averaging methodology and applicable reuse terms; review candidates at their original state rural/urban scope. |
| 12 | EV policy register | Missing notifying orders/amendments, validity and charging eligibility review, reuse evidence, human verification records with model/prompt stamps. |
| 12 | NHAI WSA observations | Reuse and identity review, current dated status and explicit EV-charging evidence where claimed; historical directory/tender does not prove an operating charger. |
| 12 / 2 | Geography and original datasets | Reviewed district joins/service areas, monthly VAHAN, public charger inventory, tariff orders, boundaries and highways. OSM proximity requires no guessed district join. |
| 13 | Supply-hour report context | Finest genuinely published scope and definition, area-average wording, no conversion into site outage hours. |
| 13 | DISCOM performance | Verified serving utility; neutral AT&C observation with edition. State presence alone never assigns it. |
| 13 | Policies in force/expired | Human-verified dated register, amendments/supersession and applicability. Public labels never change subsidy arithmetic automatically. |
| 13 | Monthly EV growth and EV/charger ratios | Compatible reviewed monthly registrations and deduplicated public charger definitions/time coverage; state comparison. Existing annual VAHAN behavior is preserved. |
| 13 | Announced stations | Current dated, explicitly EV-charging WSA evidence within 10 km on the same verified NH. Unknown flags/planned amenities do not count as open chargers. |
| 13 | Optional AADT context | Licensed count dataset, same-NH point association and defined distance; fees/revenue are not counts. |
| 13 | Publication/deployment | Separately publish the report rebuild for exact section-08 placement; configure the pinned source release and test a newly generated stored report/PDF in the deployment environment. |

Even if another source is activated later, this checkpoint marks it
`not_integrated` rather than silently using it. Implement and test each deferred
report consumer after its gate passes. Never re-enrich a customer's old report.

## Validation

Backend regression tests cover old/new verbatim reads, missing and pending
sources, null voltage, unverified ledger completeness, unchanged financials,
capacity confirmation, release configuration and source stamps. Six actual
PostGIS cases use a read-only transaction with no database writes. Frontend
checks cover absent/verified conditions and stored kVA wording. Browser/PDF
acceptance uses test payloads on built frontends, including old/new/missing
context and desktop/mobile layouts. Existing archived PDF immutability tests
are unchanged. Known large-chunk warnings remain Part 9 work.
