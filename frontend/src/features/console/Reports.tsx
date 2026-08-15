import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/** PART C.6 (needs 5,7) — placeholder. Ships when the data behind it ships. */
export function Reports() {
  return (
    <>
      <PanelHeader
        title="Reports"
        note="Every report generated, what verdict it gave, which assumptions in it are still unverified, and — once a lead is handed to a network — the chain that proves the lead was ours."
      />
      <Glossary terms={["Breakeven utilisation", "Tier", "Confidence"]} />
      <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
        Not built yet — depends on C.6 (needs 5,7).
      </p>
      <p className="mt-3 max-w-prose text-[13px] text-ink-muted">
        The verdict split shown here is also the number we publish openly: if the commission on a
        handed-off lead could quietly bend a verdict, the whole product is worthless, so the ratio
        of Build to Don't-build is published before the first commission is earned.
      </p>
    </>
  );
}
