import { NavLink } from "react-router-dom";

import { DEMO_REPORT_ID } from "../report/payload";

/** Shared destinations for customer pages; private routes retain their own navigation. */
export function PublicNavigation() {
  const destinations = [
    ["/", "Home"],
    ["/assess", "Assess my site"],
    [`/report/${DEMO_REPORT_ID}`, "Sample report"],
    ["/data", "Data"],
    ["/owner", "Station owners"],
  ] as const;

  return (
    <nav aria-label="Main navigation" className="public-navigation">
      {destinations.map(([to, label]) => (
        <NavLink
          key={to}
          to={to}
          end={to === "/"}
          className={({ isActive }) => `public-navigation-link${isActive ? " is-current" : ""}`}
        >
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
