import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";

import { PanelHeader } from "./ConsoleLayout";
import { Glossary } from "./Glossary";

/**
 * PART C — the project itself, as a panel.
 *
 * Every milestone in the order a reader should care: the actionable queue
 * first, then what is done, then what is parked on purpose. The prose is
 * curated; the statuses and numbers come live from the database, so the page
 * cannot claim the poller is running while `poll_runs` is empty.
 */

type Milestone = {
  order: number;
  part: string;
  title: string;
  status: "done" | "code_done" | "partial" | "next" | "parked" | "not_started";
  what: string;
  evidence: string;
  to_close: string | null;
};

type Input = {
  name: string;
  kind: "key" | "endpoint" | "data" | "infra";
  status: "configured" | "missing" | "attention" | "later";
  needed_for: string;
  env_vars: string[];
  how_to_get: string;
  detail: string;
};

type ProgressOut = {
  checked_at: string;
  summary: string;
  milestones: Milestone[];
  inputs: Input[];
};

const INPUT_STATUS: Record<Input["status"], { label: string; cls: string }> = {
  configured: { label: "configured", cls: "bg-ok-ground text-ok" },
  missing: { label: "needed", cls: "bg-warn-ground text-warn" },
  attention: { label: "needs attention", cls: "bg-warn-ground text-warn" },
  later: { label: "later — don't chase yet", cls: "bg-ground-sunk text-ink-faint" },
};

/** Order inside the inputs section: actionable first, done last. */
const INPUT_ORDER: Input["status"][] = ["attention", "missing", "later", "configured"];

const MILESTONE_STATUS: Record<Milestone["status"], { label: string; cls: string }> = {
  done: { label: "done", cls: "bg-ok-ground text-ok" },
  code_done: { label: "code done, unproven", cls: "bg-info-ground text-info" },
  partial: { label: "partly live", cls: "bg-info-ground text-info" },
  next: { label: "do next", cls: "bg-warn-ground text-warn" },
  parked: { label: "parked on purpose", cls: "bg-ground-sunk text-ink-faint" },
  not_started: { label: "not started", cls: "bg-ground-sunk text-ink-faint" },
};

/** Which statuses land in which section of the page. */
const SECTIONS: { title: string; note: string; statuses: Milestone["status"][] }[] = [
  {
    title: "The queue — in order",
    note: "All of these can proceed in parallel; the order is how much each day of delay costs. Most are human work the codebase cannot do for itself.",
    statuses: ["next", "partial"],
  },
  {
    title: "Done — built and verified",
    note: "Each line says what the evidence is, not just that a box was ticked.",
    statuses: ["done", "code_done"],
  },
  {
    title: "Parked — deliberately not yet",
    note: "Each with the reason, and the event that un-parks it. Building these now would be motion, not progress.",
    statuses: ["parked", "not_started"],
  },
];

export function Progress() {
  const q = useQuery({
    queryKey: ["progress"],
    queryFn: async () => {
      const res = await fetch("/api/internal/progress", { credentials: "include" });
      if (!res.ok) throw new Error(`progress returned ${res.status}`);
      return (await res.json()) as ProgressOut;
    },
  });

  return (
    <>
      <PanelHeader
        title="Progress"
        note="What is done, what is next, and why — in order. Statuses are read from the database, so this page cannot say the poller is running while poll_runs is empty."
      />
      <Glossary terms={["Poller", "Cascade", "Nominatim", "Tier", "Occupancy", "LGD"]} />

      {q.isPending && <p className="font-data text-[13px] text-ink-faint">…</p>}
      {q.isError && (
        <p className="max-w-prose bg-warn-ground px-2 py-1 font-data text-[13px] text-warn">
          Could not read progress.
        </p>
      )}

      {q.data && (
        <>
          <p className="max-w-prose border-l-2 border-rule-strong bg-ground-sunk px-3 py-2 text-[13px] text-ink">
            {q.data.summary}
          </p>

          {SECTIONS.map((section) => {
            const items = q.data.milestones.filter((m) => section.statuses.includes(m.status));
            if (items.length === 0) return null;
            return (
              <section key={section.title} className="mt-8 max-w-4xl">
                <h2 className="mb-0.5 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
                  {section.title}
                </h2>
                <p className="mb-3 max-w-prose font-data text-[11px] text-ink-faint">
                  {section.note}
                </p>

                <ol className="border-t border-rule">
                  {items.map((m) => (
                    <li key={m.order} className="border-b border-rule py-3">
                      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                        <span className="font-data text-[11px] text-ink-faint tabular-nums">
                          {String(m.order).padStart(2, "0")}
                        </span>
                        <span className="font-data text-[11px] text-ink-faint">PART {m.part}</span>
                        <span className="font-ui text-[14px]">{m.title}</span>
                        <span
                          className={cn(
                            "px-1.5 font-ui text-[10px] tracking-[0.08em] uppercase",
                            MILESTONE_STATUS[m.status].cls,
                          )}
                        >
                          {MILESTONE_STATUS[m.status].label}
                        </span>
                      </div>

                      <p className="mt-1.5 max-w-prose text-[13px] text-ink-muted">{m.what}</p>

                      <p className="mt-1.5 max-w-prose font-data text-[12px]">
                        <span className="text-ink-faint">Where it stands: </span>
                        {m.evidence}
                      </p>

                      {m.to_close && (
                        <p className="mt-1 max-w-prose font-data text-[12px]">
                          <span className="text-ink-faint">To close it: </span>
                          {m.to_close}
                        </p>
                      )}
                    </li>
                  ))}
                </ol>
              </section>
            );
          })}

          <section className="mt-10 max-w-4xl">
            <h2 className="mb-0.5 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
              Keys &amp; inputs — what only you can provide
            </h2>
            <p className="mb-3 max-w-prose font-data text-[11px] text-ink-faint">
              Every account, key, endpoint, file and machine the project needs, with the exact .env
              lines each one fills. The workflow: make the account, set the spending cap in the
              provider&apos;s own console, paste the lines into .env, restart the API — this page
              reads live settings, so the row flips to “configured” on its own.
            </p>

            <ol className="border-t border-rule">
              {[...q.data.inputs]
                .sort((a, b) => INPUT_ORDER.indexOf(a.status) - INPUT_ORDER.indexOf(b.status))
                .map((i) => (
                  <li key={i.name} className="border-b border-rule py-3">
                    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                      <span className="font-ui text-[14px]">{i.name}</span>
                      <span className="font-data text-[10px] text-ink-faint uppercase">
                        {i.kind}
                      </span>
                      <span
                        className={cn(
                          "px-1.5 font-ui text-[10px] tracking-[0.08em] uppercase",
                          INPUT_STATUS[i.status].cls,
                        )}
                      >
                        {INPUT_STATUS[i.status].label}
                      </span>
                    </div>

                    <p className="mt-1 max-w-prose text-[12px] text-ink-muted">{i.needed_for}</p>
                    <p className="mt-1 max-w-prose font-data text-[12px]">
                      <span className="text-ink-faint">Right now: </span>
                      {i.detail}
                    </p>
                    {i.status !== "configured" && (
                      <p className="mt-1 max-w-prose font-data text-[12px]">
                        <span className="text-ink-faint">How: </span>
                        {i.how_to_get}
                      </p>
                    )}
                    {i.env_vars.length > 0 && i.status !== "configured" && (
                      <pre className="mt-1.5 max-w-prose overflow-x-auto bg-ground-sunk px-2 py-1 font-data text-[11px]">
                        {i.env_vars.join("\n")}
                      </pre>
                    )}
                  </li>
                ))}
            </ol>
          </section>

          <p className="mt-6 font-data text-[11px] text-ink-faint">
            Checked {new Date(q.data.checked_at).toLocaleString()}. Deeper detail lives in
            FINDINGS.md (what each tick does not cover) and PLAN.md (the full build order).
          </p>
        </>
      )}
    </>
  );
}
