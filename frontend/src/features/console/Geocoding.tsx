import { PanelHeader } from "./ConsoleLayout";

/** PART C.2 (needs 1.3) — placeholder. Ships when the data behind it ships. */
export function Geocoding() {
  return (
    <>
      <PanelHeader
        title="Geocoding"
        note="Cascade funnel by level, manual queue depth, disagreements over 2 km, and cost per resolved address."
      />
      <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
        Not built yet — depends on C.2 (needs 1.3).
      </p>
    </>
  );
}
