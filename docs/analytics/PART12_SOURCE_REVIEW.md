# Part 12 acquisition review — 2026-10-01

One of the five expansion datasets is now available: **7,726 OSM power
observations**. The other four remain pending. Acquisition is separate from
accepting a source for public reuse or applying its values to a report.

Original downloads, checksums, PDF text, selected page renders and private
candidates are archived in `local_scratch/source_review/part12_20261001/`.
`downloads.json` records actual retrieval times and final URLs. Raw PDFs and
the 558 MB PBF are excluded from the public build. The adjacent committed
[source index](PART12_SOURCE_INDEX.json) preserves artifact identities.

## OSM power

Source: [Geofabrik Southern Zone extract](https://download.geofabrik.de/asia/india/southern-zone-260930.osm.pbf),
snapshot **2026-09-30T20:22:42Z**, retrieved 2026-10-01.
SHA256 `24f97508305830d91483723c06fdc5c705c49c75ad81a46db51cdb74094879a7`;
the publisher's MD5 was also checked. Data retains
[OpenStreetMap contributors' ODbL licence and attribution](https://www.openstreetmap.org/copyright).
The derived CSV is available under ODbL with its source metadata; no blanket
CC BY licence is applied to it.

Automated acquisition review: exact allowlist, source checksum, replication
timestamp, object IDs, nulls, coordinates, shared schema and reproducible
transformation `osm_power_first_vertex_v1`. This is not a utility survey or
human certification of the equipment. The isolated offline extractor is
`scripts/extract_public_osm_power.py` with `osmium==4.2.0`. Run its regression
tests with that isolated package on `PYTHONPATH`.

- 2,398 nodes retain mapped coordinates; 5,328 ways use their first mapped
  perimeter vertex. That vertex is not a centroid or surveyed equipment center.
- Seven power relations are excluded; no unresolved ways were exported.
- Every district code remains null. The extract is regional; no state or
  district assignment is inferred. State/district lookups therefore return
  no matching observations until a separate reviewed geography join exists.
- Voltage is a verbatim, unverified OSM tag. Capacity, access, ownership,
  connection feasibility and equipment health remain unknown. Missing mapping
  does not establish absence. User and changeset identifiers are excluded.

## DISCOM performance

The migrated [PFC performance page](https://www.pfcindia.co.in/pages/operations/performance-report-of-power-utilities)
was resolved through the public website's CMS. Three genuine PDFs are archived:
2024-25 (February 2026), 2023-24 (October 2025), and 2022-23 (updated April 2024).
The previous URLs now return the website shell, not the PDFs.

**Commercial reuse is blocked.** PDF page 2 of the two newest editions restricts
redistribution and permits information use for non-commercial purposes with
acknowledgement. Obtain written permission for Chargeworthy's commercial
website and assessment/report use before activating figures or publishing the
PDFs. The contact printed in those editions is `ra_alex@pfcindia.com`.

The latest edition's Annexure 1.8 spans PDF pages 82–87 and contains three
reporting years. Prefer compatible observations from that edition; overlapping
years in older editions can be restated and are not extra independent samples.
Human-check table/page, AT&C definition and signed ACS–ARR gap basis, integer
paise conversion, utility identities and service jurisdictions. State presence
alone never identifies a site's serving utility.

## Supply hours

The [CEA state table](https://cea.nic.in/wp-content/uploads/dm/2025/09/State_wise_Average_hours_of_Supply_in_a_day_HHhh_for_FY_2018_19_to_FY_2023_2024_as_per_NPP_Portal.pdf)
is archived and page 1 was visually checked. Coordinate-aligned extraction
prepared **34 private review observations** for Karnataka, Kerala and Tamil Nadu
over FY 2018-19 to 2023-24. Kerala and Tamil Nadu each have an empty 2018-19
urban cell; those observations were omitted, never replaced with zero or shifted
into an adjacent column. Values retain the printed HH.hh representation.

Confirm decimal-hour methodology and the calculation of averages before
activation. These are rural/urban state averages for 11 kV feeders, not monthly
measurements, district uptime or site outage hours. The upload folder is not
the observation or verified publication date.

The archived [legacy CEA copyright policy](https://cea.nic.in/old/websitepolicy.html)
allows accurate, attributed reproduction with a third-party exception. Confirm
its applicability to the current PDF and NPP-attributed data; the current
website-policy page alone did not establish that permission. No NFMS public
aggregate export was acquired, and no login was bypassed.

## State EV policies

Three official PDFs are archived, with review proposals in `policy_review.json`.
Those proposals carry `model`, `prompt_version=part12_policy_review_v1` and
`human_verified=false`. Amounts remain null; no policy, tariff, subsidy or ROI
input has been written or approved.

| State | Evidence | What must be reviewed before activation |
| --- | --- | --- |
| Kerala | [NSWS government order](https://www.nsws.gov.in/s3fs/2022-12/pdf_Electric-Vehicle-policy_2%20%284%29_0.pdf), GO(Ms) No.24/2019/Trans, 10 March 2019; scanned PDF | Visually verify clauses, current validity and amendments. PDF page 8, clause 6.2.4 concerns KSEB supply/connection roles; it is not proof of a customer's subsidy entitlement. |
| Tamil Nadu | [Official 2023 policy booklet](https://storage.investingintamilnadu.com/Guidance/Uploads/Others/tn_electric_vehicles_policy_2023.pdf), PDF pages 18–19 | Obtain the notifying order and date, check later amendments and eligibility. Clause 5.1.2 includes proposed tariff revisions requiring regulator approval; it is not a current tariff order. Review 5.2.1 public charging conditions and budget limits. |
| Karnataka | [Clean Mobility Policy 2025–30](https://investkarnataka.co.in/wp-content/uploads/2025/12/Clean-mobility-policy.pdf), GO CI 117 SPI 2024(e), 11 February 2025; Gazette 12 February 2025 | Verify charging-specific clauses, effective period, supersession, eligibility and sanction conditions. Manufacturing incentives must not become charging grants by inference. |

For Tamil Nadu, inspect the actual later tax notification referenced by the
[2025 Gazette index](https://www.stationeryprinting.tn.gov.in/extra_ordinary_lists.php?id=MjAyNQ%3D%3D):
GO Ms No.674, Home (Transport-I), 29 December 2025. An index entry alone does not
verify a current benefit. Central component guidelines and amendments are still
pending. Notification reuse must also be established before public activation.

Record a human verification entry with reviewer, date, exact source checksum,
clause/page, accepted values, validity and unresolved conditions. Owner approval
cannot substitute for a publisher's reuse permission. After accepted policy
activation, compare with an explicitly supplied `subsidy_rules` JSON export
using the existing offline read-only comparison; never automatically write it.

## NHAI wayside amenities

The [historical NHAI directory](https://nhai.gov.in/nhai/sites/default/files/mix_file/NHAI_WSA_Site_Directory.pdf)
is archived (21 pages; March 2021 bidding schedule). It does not establish
current operational or awarded status.

A [current official tender listing](https://www.etenders.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndTendersByOrganisation&service=direct&sp=SBHgI013YJrPRYhqXDt5TRg%3D%3D)
was also archived: `2026_NHAI_292687_2`, published 30 September 2026,
NH52 Solapur–Vijayapura, chainage 98+800 RHS, Bhutnal, Karnataka.
This is dated tender evidence, not an award, operational amenity or verified
charger. Its charging flag remains unknown; coordinates and district are null.
The private candidate preserves the listing's title and tender identifier.

Confirm directory/listing reuse, human-review site identity and printed status,
and acquire award/charging evidence where claimed. Do not geocode chainage or
allow planned amenities to shorten verified charger gaps.

## Remaining owner actions

1. Obtain PFC's written commercial reuse permission; a draft is prepared beside
   the archive. Nothing has been sent.
2. Review and sign the policy proposals after the missing notification,
   amendment and applicability evidence has been acquired. Financial inputs
   still require the existing human-verification process.
3. Supply permission evidence or authorized exports if CEA/NPP/NHAI cannot
   establish the required reuse and methodology. Missing sources remain pending.

Part 12's full five-source delivery is not complete. Parts 13–16 must use only
available reviewed sources and preserve explicit missing/unverified context.

## Deferred follow-up

The owner requested that the remaining Parts 12 and 13 work be kept for later.
The resume checklist is in [PART13_REPORT_CONTEXT.md](PART13_REPORT_CONTEXT.md).
OSM report integration does not complete the four pending source acquisitions.
