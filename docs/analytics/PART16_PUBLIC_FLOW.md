# Part 16 — public checklist and district context

Implemented checkpoint, 2026-10-02. Source-dependent Parts 12/13 remain deferred as requested.

The landing checklist and paced assessment share the owner-approved 34 checks in
12 / 4 / 8 / 7 / 3 groups. Each check names its available source or the evidence
still required. VAHAN records and verified EV tariff orders are explicitly
conditional on site coverage, rather than implying every district has them.
OSM power proximity remains survey-dependent; area supply is not
site outage history; a planned NHAI amenity is not an operating charging station.
The walkthrough labels bracketed values as examples and does not claim live
fetches for every check. The fictional 27 / 6 / 1 coverage split is removed.

Reports show coverage derived only from their stored site facts. The existing
contract provides an unverified flag but no measured category: verified facts
are counted as sourced and zero are labelled measured. Counts include the
optional Part 13 context facts when present. They do not assert that all 34
checklist questions have been assembled. No stored JSON or archived PDF is
rewritten; rendering the same stored data can display the new coverage caption.
The full local report has PROMISED_SITE_FACTS = 34; this part changes no promised
count or report section order. The two optional Part 13 contextual checks are
not added to the owner-approved checklist.

AssessOut adds an optional LGD district code, and the generated API schema is
updated. Working and result share YourDistrict, joined by that exact code to the
validated public build snapshot. Old saved responses without a code omit the
block rather than guessing by name. Changing the pin clears an old result.
The fourteen-second walkthrough, final hold, retry and reduced-motion behavior
are preserved. District summaries carry the six public version stamps and link
to the reviewed district slug.

Registration totals require every class/month in a completed twelve-month
period; growth requires the corresponding previous period and a positive base.
Future/incomplete current months are withheld. These are new registrations,
never fleet size. Policy context uses reviewed notification/validity dates,
inclusive expiry and supersession; unknown end dates do not establish a
confirmed interval. Source links retain retrieval dates. No subsidy eligibility
or serving utility is inferred. The frontend uses the same build snapshot as
/data; refreshing a result does not preserve public-context values historically.
The assessment teaser and persisted reports remain unchanged.

The home section promotes Electricity or planned highway amenities only when
reviewed, eligible observations exist. Current production datasets for those
links are still pending, so no live-data claim is shown.

## Still pending

- Compatible district fleet counts and public-charger inventory for EVs per
  public charger; registration flows cannot substitute for the fleet.
- A reviewed serving-DISCOM service-area join or site confirmation.
- Production monthly registration and policy observations, plus real-data
  acceptance after source review. Current four-fact blocks show explicit gaps.
- Emission/verification of all 34 promised site checks in the published report;
  unsupported checks remain named pending requirements, not fabricated facts.
- Original Part 9 launch acceptance, including owner grid privacy and PDF paths.

## Validation

Tests cover exact LGD matching, null/old responses, complete/incomplete periods,
zero bases, future observations, policy expiry/supersession, source-gated home
links, stored-fact coverage and the unchanged paced transition. Production build,
public-data validation/privacy scans and desktop/mobile browser captures are
checked before this checkpoint is pushed. No production database operation,
paid API call or source acquisition is part of this checkpoint.

Final checkpoint evidence: 172 frontend tests passed with a 15-second test
budget for Windows source-validation subprocesses; six teaser arithmetic tests
passed. The local 12-section ReportBuild pin and context tests passed (19 tests).
Clean and local builds passed their 829/837 artifact privacy scans. At 1440px
and 390px, pending and private invented active-context cases, working screens,
checklist labels, stored-report renders and the PDF path passed without overflow
or page errors. The finish reviewer scored its source-availability wording fix
resolved. Ruff and targeted TypeScript ESLint checks passed; the repository has
no flat ESLint config, so the targeted check used a local, uncommitted recommended
configuration. No project lint configuration was added.
