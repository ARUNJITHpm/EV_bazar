# Part 15 — public grid, policy and corridor context

Available-source implementation checkpoint, 2026-10-02. This is not completion
of live source acquisition or corridor gap calculation.

## Implemented

- Electricity: reviewed AT&C observations by state/utility and historical small
  multiples. Every chart and CSV retains the required outage/voltage warning.
  An explicitly published national reference must match edition, fiscal year and
  metric basis; no average of utilities substitutes for it. Conflicting editions,
  duplicate utility observations and future fiscal years are withheld.
- Supply hours: separate published periods, definitions and rural/urban coverage;
  missing data stays missing and an observed zero remains zero. Future periods
  and ambiguous observations are withheld. Per-observation sources remain visible.
- Policy register: notification links, validity, expired/future/superseded states
  and build-date status. `valid_to` is the inclusive last valid day in this public
  register. An absent end date is labelled unknown, not asserted to be in force.
- Vehicles: state registration charts with dated policy markers on monthly
  categories, an accessible notification/date list, and a causation warning.
  Missing months break lines. An incomplete reference-district/class/month is
  withheld. District registration charts carry the same state policy context.
- Districts: Grid and policy block, source dates and explicit state-versus-district
  coverage. Serving utilities are never inferred from a statewide performance row.
  An EV fleet-to-charger ratio is explicitly unavailable: annual new registrations
  are not the fleet denominator. Existing registrations-based ratios are retained
  with their original counting-unit limitation.
- Corridors: separate dated planned/awarded EV amenities, drawn with hollow symbols
  and labelled as unverified chargers. Unknown charging flags, historical rows,
  future dates, conflicting latest records and superseded statuses are withheld.
  Amenities cannot establish or shorten any gap; no gap length is emitted.
- Existing metadata drives Sources; pending source anchors and methodology explain
  the new measures. Existing Chart controls, table and CSV downloads are reused.
  CSV context now retains chart notes, policy markers and national references.
  All six output stamps remain. Existing page identity and tokens are preserved.

## Data boundary and national-reference convention

`virtual:analytics-expansion` is built only from validated `data/public` artifacts.
It does not read owner tables, private grid details, report payloads or predictions.
The as-of date is frozen at the build in IST for consistent prerender and client
status. Refresh/rebuild is required to advance it. Production reads no fixtures.

A PFC national observation uses `state=India` and `discom_id=national` together;
the public loader refuses either sentinel used separately. It requires the same
reviewed provenance/schema as utility observations. `discom_id=state_total` is an
aggregate, not a named utility. National rows cannot assign a serving utility or
become district-level context. The national row must be transcribed from the
source, never calculated from utility observations.

## Remaining work, deliberately visible

1. Complete the deferred Part 12 source gates: PFC commercial reuse and reviewed
   comparable national figures; CEA method/reuse; notified state-policy amendments
   and human review; NHAI reuse and dated explicit EV-charging evidence. Currently
   all four datasets remain pending, so the new pages show no invented live data.
2. Add a reviewed serving-DISCOM geographic crosswalk before district utility
   performance can be shown. State performance must not be attributed to a pin.
3. Acquire compatible EV fleet counts and a reviewed public-charger counting unit
   before district/state EVs-per-charger comparisons can be published.
4. Corridor gap calculation and its map are still to implement after a reviewed
   operating DC-fast inventory and connected NH route evidence exist. The current
   public charger schema is inventory, not a verification of operating status.
   A reviewed snap tolerance belongs in metadata. Gap distance must follow the
   same verified connected route using PostGIS geography in EPSG:4326; reject
   disconnected geometry, ambiguous carriageways and unresolved route joins.
   Never use straight-line point distances or planned amenities as gap endpoints.
5. Live dataset acceptance must compare charts/tables/CSV/markers to the archived
   source tables; private browser fixtures demonstrate behavior, not acquisition.
   Final Part 9 launch acceptance is still due after Part 16.

No new database migration, external acquisition, model run, economics change or
production deployment is part of this checkpoint. Parts 12/13 remain deferred.

## Validation

The clean publication checkout passes 161 frontend tests, including national
scope validation, null/zero supply, policy validity/supersession and dates,
reference-line/marker rendering and downloads, and planned-amenity separation.
Production builds in publication and local checkouts pass TypeScript, prerender
and private-grid artifact refusal. Desktop/mobile browser acceptance covers
source-missing production pages and private intercepted populated test cases.
The latter remain under local_scratch and never enter public data or builds.
Existing large-chunk warnings and other Part 9 launch gaps remain recorded.
