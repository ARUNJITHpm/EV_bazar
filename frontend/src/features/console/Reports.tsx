import { PanelHeader } from "./ConsoleLayout";

/** PART C.6 (needs 5,7) — placeholder. Ships when the data behind it ships. */
export function Reports() {
  return (
    <>
      <PanelHeader
        title="Reports"
        note="Reports generated, verdict split, unresolved warnings, and the attribution chain end to end."
      />
      <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
        Not built yet — depends on C.6 (needs 5,7).
      </p>
    </>
  );
}
