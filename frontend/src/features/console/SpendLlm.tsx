import { PanelHeader } from "./ConsoleLayout";

/** PART C.3 — placeholder. Ships when the data behind it ships. */
export function SpendLlm() {
  return (
    <>
      <PanelHeader
        title="Spend · LLM"
        note="Tokens in and out by model and by purpose, retry cost shown separately, and the queue pending human verification."
      />
      <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
        Not built yet — depends on C.3.
      </p>
    </>
  );
}
