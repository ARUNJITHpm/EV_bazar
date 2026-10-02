import { NavLink } from "react-router-dom";

import { DEMO_REPORT_ID } from "../report/payload";

/** Shared destinations for customer pages; private routes retain their own navigation. */
export function PublicNavigation({ theme = "dark" }: { theme?: "dark" | "paper" }) {
  const ink =
    theme === "paper"
      ? "text-cw-paper-muted hover:text-cw-ink"
      : "text-cw-muted hover:text-cw-text";
  const current = theme === "paper" ? "text-cw-ink" : "text-cw-text";
  const destinations = [
    ["/", "Home"],
    ["/assess", "Assess my site"],
    [`/report/${DEMO_REPORT_ID}`, "Sample report"],
    ["/data", "Data"],
    ["/owner", "Station owners"],
  ] as const;

  return (
    <nav
      aria-label="Main navigation"
      className="flex flex-wrap items-center gap-x-5 gap-y-1 font-cw-sans text-[15px]"
    >
      {destinations.map(([to, label]) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) =>
            `inline-flex min-h-[44px] items-center transition-colors duration-200 ${isActive ? `${current} font-semibold underline underline-offset-4` : ink}`
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
