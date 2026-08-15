import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/** PART C.3 — placeholder. Ships when the data behind it ships. */
export function SpendLlm() {
  return (
    <>
      <PanelHeader
        title="Spend · LLM"
        note="What the language models have cost, split by model and by what we asked them to do — with retries counted separately, because a retry is a cost that bought nothing. The first use comes at PLAN 3.1, reading tariff PDFs."
      />
      <Glossary terms={["Cap", "Price card", "Paise"]} />
      <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
        Not built yet — depends on C.3.
      </p>
      <p className="mt-3 max-w-prose text-[13px] text-ink-muted">
        No model has been called yet. The first caller will be tariff extraction (PLAN 3.1), and
        every extraction is checked by a human before it can reach a report.
      </p>
    </>
  );
}
