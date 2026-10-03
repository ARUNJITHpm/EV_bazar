import { useEffect, useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";

import { PublicNavigation } from "./PublicNavigation";
import { Wordmark } from "./Wordmark";

/** The same brand bar on every customer route; page controls belong below it. */
export function PublicHeader({ children }: { children?: ReactNode }) {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  useEffect(() => setOpen(false), [pathname]);
  return (
    <header className="public-header no-print">
      <div className="public-container public-header-row">
        <Link to="/" className="public-wordmark">
          <Wordmark />
        </Link>
        <button
          type="button"
          className="public-menu-toggle"
          aria-expanded={open}
          aria-controls="public-menu"
          aria-label={open ? "Close navigation" : "Open navigation"}
          onClick={() => setOpen(!open)}
        >
          {open ? <X size={20} aria-hidden="true" /> : <Menu size={20} aria-hidden="true" />}
          Menu
        </button>
        <div
          id="public-menu"
          className="public-menu"
          data-open={open}
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              setOpen(false);
              (event.currentTarget.previousElementSibling as HTMLButtonElement | null)?.focus();
            }
          }}
        >
          <PublicNavigation />
        </div>
      </div>
      {children && (
        <div className="public-context">
          <div className="public-container public-context-row">{children}</div>
        </div>
      )}
    </header>
  );
}
