# Part 14: private grid records and erasure plan

Written before the migration, 2026-10-02. Owner grid information is optional,
private display context. Existing anonymous-analysis consent does not authorize
using these new fields in training, peer averages or other customers' reports.

- Save requires explicit consent to store grid details privately. A station's
  existing owner session and server ownership check protect every read/write.
- Normal corrections insert dated revisions; earlier records are never updated.
  The latest revision is the current view. Unknown numeric values remain null;
  connected kW and sanctioned kVA remain separate.
- Grid-consent withdrawal deletes **every** grid revision, monthly outage
  revision and private grid consent record for that station in one transaction.
  It does not delete the station or bills and requires new explicit consent
  before grid data can be saved again. There is no retained grid audit trail.
- “Delete my data” and inactivity erasure delete all grid/outage/consent records
  before deleting stations. An erasure test checks all versions and ownership
  isolation. No protected event table is updated or deleted.
- No derived grid cache, export, model feature, prediction context or report
  copy is created. No grid values enter the public validator/export or /data.
  Public area observations stay in the existing immutable public-reference cache.
- New private endpoints send `Cache-Control: no-store`. The form is kept only
  in component memory, never browser storage. React Query grid/area caches are
  cleared on sign-out and account deletion. Withdrawal cancels in-flight grid reads and overwrites the grid cache with an empty result; the public area context remains.
- Operational logs must not record request/response bodies for these routes.
  Backup retention and erasure replay on restore are operational release requirements; a restored backup must replay erasures before serving owner data. This code does not configure
  backup retention or claim deletion from an external backup system.

The published migration uses revision `0022_owner_grid`, descending from `0020`;
`0021` is reserved for an unrelated unpublished analytics draft. The local
workspace already contains a duplicate `0019` draft and that unpublished branch.
They are preserved. Validate/apply the clean published chain, not the mixed draft
directory; this checkpoint never migrates the production database.

Source-dependent area facts from Parts 12/13 remain deferred. The owner card
shows explicit missing states and source coverage, without inventing registrations,
growth, charger ratios, serving utility, tariff entitlement or policies in force.


## Ownership review release gate

`OWNER_GRID_VERIFIED_STATIONS` defaults to `{}`. Deployment staff may provide a
JSON object mapping an exact database station ID to a non-empty, retained manual
review reference, for example `{"123":"ownership-review/2026-10-02/123"}`. Verify
station authority against actual evidence before adding an entry. Do not infer
ownership from a phone number, login or the fields the owner submits. This is an
operations-controlled register, never a frontend field. Its reference is stored
with explicit private-display consent; do not put personal evidence in the value.
Invalid configuration fails closed; absent review blocks collection with 403 and
the UI explains why. Withdrawal remains available after a review is revoked.
A dedicated verification/review console and evidence retention are deferred.

Apply `0022_owner_grid` only from the clean published migration chain after the
normal release review. PostgreSQL triggers reject UPDATE on all three private
revision/consent tables; explicit privacy DELETE remains supported. Local checks
use SQLite API transactions and offline PostgreSQL SQL generation, so executing
migration/trigger checks against a disposable PostgreSQL database remains a
release requirement. No live migration was run in this checkpoint.

Run `npm run build` for the public artifact privacy gate; it rejects private grid
keys in public payloads and a private test canary anywhere in built artifacts.
Shared SPA owner form/schema code is intentionally excluded from field-name
checks; the canary check still covers JavaScript and source maps.


## Checkpoint validation

The owner API/erasure suite and public artifact refusal tests pass (62 tests).
Public-reference regressions also passed (19 tests). The clean frontend regression suite passes (149 tests); the final owner
suite covers missing values, ownership gating, unit separation, network-error
drafts, withdrawal and late-save-after-logout cache isolation. Both local and
clean publication builds pass the generated API types and privacy artifact scan.
Desktop/mobile browser checks exercise save, withdrawal, blocked collection and
layout in both builds. The published Alembic graph has one head; offline SQL
includes three private tables and their UPDATE rejection triggers. No production
migration or private customer data collection occurred.
