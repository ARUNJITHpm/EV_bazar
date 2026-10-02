export interface CoveredFact {
  source: string;
  unverified: boolean;
}
export function factCoverage(facts: readonly CoveredFact[]) {
  // The stored contract has no verified measurement category. Treat verified
  // observations as sourced rather than guessing which ones were measured.
  const unverified = facts.filter((fact) => fact.unverified).length;
  return { measured: 0, sourced: facts.length - unverified, unverified, total: facts.length };
}
export function FactCoverage({ facts }: { facts: readonly CoveredFact[] }) {
  const counts = factCoverage(facts);
  return (
    <p className="my-4 text-[14px]">
      {counts.total} recorded site facts: {counts.measured} labelled measured, {counts.sourced}{" "}
      sourced, {counts.unverified} unverified. Counts describe this stored report, not the full
      34-question checklist.
    </p>
  );
}
