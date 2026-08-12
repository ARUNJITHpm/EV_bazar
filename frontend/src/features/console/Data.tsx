import { PanelHeader } from "./ConsoleLayout";

/** PART C.5 (needs 0.1) — placeholder. Ships when the data behind it ships. */
export function Data() {
  return (
    <>
      <PanelHeader
        title="Data"
        note="Per-source ingest, coverage against the tier table, dedupe stats, and the failed/closed station hunt (Rule 3)."
      />
      <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
        Not built yet — depends on C.5 (needs 0.1).
      </p>
    </>
  );
}
