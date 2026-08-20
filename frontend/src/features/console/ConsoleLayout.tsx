import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/lib/utils";

import { Login } from "./Login";

/**
 * PART C.0 - the console shell.
 *
 * Unlike the customer report, this is allowed to look like a normal admin
 * tool. It is internal, it is dense, and nobody is being persuaded by it.
 *
 * The shell asks the SERVER who it is talking to and renders accordingly.
 * This is presentation, not protection: every console endpoint refuses on its
 * own, so what follows only decides which screen to draw, never what may be
 * read (PLAN C.0).
 */

type Item = { to: string; label: string; hint: string; end?: boolean };
type Group = { heading: string | null; items: Item[] };

const NAV: Group[] = [
  {
    heading: null,
    items: [
      { to: "/console", label: "Overview", hint: "health · spend today · poller", end: true },
    ],
  },
  {
    heading: "Explain",
    items: [
      { to: "/console/concept", label: "Concept", hint: "the report · doctrine · funnel" },
      { to: "/console/progress", label: "Progress", hint: "done · next · parked, in order" },
      { to: "/console/lookup", label: "Lookup", hint: "a point → district, with the working" },
      { to: "/console/data", label: "Data", hint: "tables · what each holds · tiers" },
    ],
  },
  {
    heading: "Sources",
    items: [
      { to: "/console/cpo", label: "CPO", hint: "partners · terms · uptime" },
      { to: "/console/competitors", label: "Competitors", hint: "inventory · networks · DC-fast" },
      { to: "/console/geocoding", label: "Geocoding", hint: "cascade · manual queue" },
    ],
  },
  {
    heading: "Demand",
    items: [{ to: "/console/vahan", label: "VAHAN", hint: "EV counts · growth · by class" }],
  },
  {
    heading: "Spend",
    items: [
      { to: "/console/spend/maps", label: "Maps & APIs", hint: "calls · quota · ₹" },
      { to: "/console/spend/llm", label: "LLM", hint: "tokens · models · ₹" },
    ],
  },
  {
    heading: "Output",
    items: [{ to: "/console/reports", label: "Reports", hint: "verdicts · leads · attribution" }],
  },
];

type Session = { state: "in"; operator: string } | { state: "out" } | { state: "unconfigured" };

export function ConsoleLayout() {
  const session = useQuery<Session>({
    queryKey: ["console-me"],
    // A 401 is the expected answer for a signed-out operator, not a network
    // failure, so it is returned as data rather than thrown.
    queryFn: async () => {
      const res = await fetch("/api/internal/console/me", { credentials: "include" });
      if (res.ok) {
        const body = (await res.json()) as { operator: string };
        return { state: "in", operator: body.operator };
      }
      return res.status === 503 ? { state: "unconfigured" } : { state: "out" };
    },
    // Re-check on focus: a session that expired while the tab sat open should
    // surface as the login screen, not as every panel failing at once.
    refetchOnWindowFocus: true,
    staleTime: 60_000,
  });

  async function signOut() {
    await fetch("/api/internal/console/logout", { method: "POST", credentials: "include" });
    await session.refetch();
  }

  if (session.isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ground">
        <p className="font-data text-[13px] text-ink-faint">…</p>
      </div>
    );
  }

  if (session.data?.state === "unconfigured") {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ground text-ink">
        <div className="max-w-lg border border-rule p-6">
          <p className="mb-2 font-ui text-[11px] font-bold tracking-[0.08em] text-warn uppercase">
            Console auth is not configured
          </p>
          <p className="max-w-prose text-sm text-ink-muted">
            The endpoints are refusing every request, which is the correct behaviour — an
            unconfigured console must not be an open one. Generate a password and secret key:
          </p>
          <pre className="mt-3 overflow-x-auto bg-ground-sunk p-2 font-data text-[12px]">
            uv run python -m scripts.console_password
          </pre>
          <p className="mt-2 font-data text-[11px] text-ink-faint">
            Paste both lines into <code>.env</code> and restart the API.
          </p>
        </div>
      </div>
    );
  }

  if (session.data?.state !== "in") {
    return <Login onSignedIn={() => void session.refetch()} />;
  }

  return (
    <div className="flex min-h-screen bg-ground text-ink">
      <aside className="w-64 shrink-0 border-r border-rule">
        <div className="border-b-2 border-rule-strong px-4 py-3">
          <p className="font-ui text-[11px] font-bold tracking-[0.08em] uppercase">
            EV Site Intelligence
          </p>
          <p className="font-data text-[11px] text-ink-faint">operations console</p>
        </div>

        <nav className="p-2">
          {NAV.map((group) => (
            <div key={group.heading ?? "root"} className="mb-4">
              {group.heading && (
                <p className="px-2 py-1 font-ui text-[10px] font-bold tracking-[0.08em] text-ink-faint uppercase">
                  {group.heading}
                </p>
              )}
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    cn(
                      "block border-l-2 px-2 py-1.5 transition-colors",
                      isActive
                        ? "border-rule-strong bg-ground-sunk"
                        : "border-transparent hover:bg-ground-sunk",
                    )
                  }
                >
                  <span className="block font-ui text-[13px]">{item.label}</span>
                  <span className="block font-data text-[10px] text-ink-faint">{item.hint}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="border-t border-rule px-4 py-3">
          <p className="font-data text-[11px] text-ink-faint">{session.data.operator}</p>
          <button
            type="button"
            onClick={() => void signOut()}
            className="mt-1 font-ui text-[12px] text-ink-muted underline underline-offset-2 hover:text-ink"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 p-8">
        <Outlet />
      </main>
    </div>
  );
}

/** Shared page heading, so every panel reads the same way. */
export function PanelHeader({ title, note }: { title: string; note: string }) {
  return (
    <header className="mb-6 border-b border-rule pb-2">
      <h1 className="font-ui text-[11px] font-bold tracking-[0.08em] text-ink-muted uppercase">
        {title}
      </h1>
      <p className="mt-1 max-w-prose text-sm text-ink-muted">{note}</p>
    </header>
  );
}
