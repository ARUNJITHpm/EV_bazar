import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/** PART C.2 — placeholder. Ships when the data behind it ships. */
export function SpendMaps() {
  return (
    <>
      <PanelHeader
        title="Spend · Maps"
        note="What the paid map and geocoding providers have cost this month, how close that is to the cap, and where it is heading by month end. Cost per address and the free-share funnel already live on the Geocoding panel."
      />
      <Glossary terms={["Cap", "Price card", "Paise", "Append-only"]} />
      <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
        Not built yet — depends on C.2.
      </p>
      <p className="mt-3 max-w-prose text-[13px] text-ink-muted">
        Nothing has been spent so far: no paid provider has a key configured, and a paid level the
        cascade cannot price is a level it refuses to assemble at all.
      </p>
    </>
  );
}
