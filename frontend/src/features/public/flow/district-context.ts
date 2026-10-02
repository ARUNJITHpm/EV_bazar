import type { PublicCatalogue } from "../../analytics/data/schemas";
import { publicDataVersions } from "../../analytics/data/schemas";
import type { Atlas } from "../../analytics/districts/model";
import { latestMonth, monthOffset, registrationTotal } from "../../analytics/districts/model";
import type { Expansion } from "../../analytics/expansion/model";
import { policyRows, policyStatus } from "../../analytics/expansion/model";

export function districtContext(
  code: number | null | undefined,
  catalogue: PublicCatalogue,
  atlas: Atlas,
  expansion: Expansion,
) {
  const district = catalogue.districts.find((row) => row.lgd_code === code);
  if (!district) return null;
  const source = (id: string) => catalogue.datasets.find((row) => row.id === id)?.metadata;
  const eligibleAtlas = {
    ...atlas,
    registrations: source("ev_registrations")
      ? atlas.registrations.filter(
          (row) => row.month <= monthOffset(expansion.asOf.slice(0, 7), -1),
        )
      : [],
  };
  const end = latestMonth(eligibleAtlas);
  const total = registrationTotal(eligibleAtlas, district.lgd_code, end);
  const prior = end
    ? registrationTotal(eligibleAtlas, district.lgd_code, monthOffset(end, -12))
    : null;
  const growth = total != null && prior != null && prior > 0 ? (total / prior - 1) * 100 : null;
  const policies = source("state_ev_policies")
    ? policyRows(expansion.policies, expansion.asOf, district.state_name)
    : [];
  const active = policies.filter((row) =>
    policyStatus(row, expansion.asOf, policies).startsWith("In force"),
  );
  return {
    district,
    versions: { ...publicDataVersions, renderer_version: "assessment_district_context_v1" },
    facts: [
      {
        label: "EV registrations and growth",
        value:
          total == null
            ? "Not available yet"
            : `${total.toLocaleString("en-IN")} new registrations · ${growth == null ? "growth unavailable" : `${growth >= 0 ? "+" : ""}${growth.toFixed(1)}% year on year`}`,
        note:
          total == null
            ? "A complete district monthly series is required."
            : `12 months through ${end}; new registrations, not the complete EV fleet.`,
        source: source("ev_registrations"),
      },
      {
        label: "EVs per public charger",
        value: "Not available yet",
        note: "A compatible fleet count and public-charger inventory are required; new registrations cannot stand in for the fleet.",
      },
      {
        label: "Serving DISCOM",
        value: "Not confirmed",
        note: "A reviewed service-area join or utility confirmation is required. State-level utility data does not identify the site's supplier.",
      },
      {
        label: "Policy in force",
        value: active.length ? active.map((row) => row.policy_name).join("; ") : "Not confirmed",
        note: `As of ${expansion.asOf}. ${active.length ? "Policy dates do not establish this site's subsidy eligibility." : "No reviewed policy with a confirmed validity interval is available for this district."}`,
        source: source("state_ev_policies"),
      },
    ],
  };
}
