import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SAMPLES } from "../report/fixtures/samples";
import { Report } from "../report/Report";
import { REPORT_SECTIONS } from "./Concept";
import { ReportBuild, SECTIONS } from "./ReportBuild";

/**
 * Track B · R12 — the console's record of the document, pinned to the
 * document.
 *
 * Both console lists describing the report are hand-kept prose, and prose
 * cannot be type-checked. The failure mode is not hypothetical: Concept's
 * section list DID describe a report the customer was not receiving, for
 * three days between the rebuild and 2026-09-06, and nothing caught it.
 *
 * So the lists are pinned here against the rendered article. A section
 * renamed, reordered, split or dropped fails this file, which is the only
 * moment anyone would find out.
 */

function renderedSections(): { id: string; eyebrow: string }[] {
  render(<Report payload={SAMPLES.build} />);
  return [...document.querySelectorAll("[data-report-section]")].map((el) => ({
    id: el.getAttribute("data-report-section") ?? "",
    // The section head's eyebrow: "01" / "Verdict", which is the document's
    // own name for itself.
    eyebrow: (el.querySelector("p")?.textContent ?? "").replace(/\s+/g, ""),
  }));
}

describe("the console's record of the twelve sections", () => {
  it("lists exactly the sections the document renders, in order", () => {
    const rendered = renderedSections();
    expect(rendered.map((s) => s.id)).toEqual(SECTIONS.map((s) => s.id));
  });

  it("gives each section the number and name the document gives itself", () => {
    const rendered = renderedSections();
    for (const [i, section] of SECTIONS.entries()) {
      const actual = rendered[i];
      expect(actual, `no rendered section at index ${i}`).toBeDefined();
      // The eyebrow renders as "01/Verdict" once whitespace is stripped, so
      // a renumbered or renamed section shows up here rather than in a
      // reader's hands.
      expect(actual?.eyebrow).toBe(`${section.n}/${section.title.replace(/\s+/g, "")}`);
    }
  });

  it("names a component file that exists", () => {
    // A renamed component leaves the record pointing at nothing, which is
    // worse than no record: it costs a search before it costs a correction.
    // Resolved by the bundler rather than off the filesystem, so the check
    // does not depend on which directory the runner was started in.
    const components = new Set(Object.keys(import.meta.glob("../report/*.tsx")));
    for (const section of SECTIONS) {
      expect(components, section.id).toContain(`../report/${section.component}`);
    }
  });

  it("keeps Concept's anatomy list in step with it", () => {
    // Two panels describe the same twelve sections for two different
    // readers. They may say different things; they may not describe
    // different documents.
    expect(REPORT_SECTIONS.map((s) => s.name)).toEqual(SECTIONS.map((s) => `${s.n} · ${s.title}`));
  });

  it("says what every section still needs, including the finished ones", () => {
    // A blank is ambiguous between "nothing left" and "nobody looked". The
    // finished sections say so in words, which is the whole point of a
    // record kept for someone picking the work up later.
    for (const section of SECTIONS) {
      expect(section.needs.length, section.id).toBeGreaterThan(0);
      expect(section.became.length, section.id).toBeGreaterThan(0);
    }
  });
});

/** The endpoint's answer for today's live database: the demo stored by
 *  economics 0.1.0, with the archive table not yet created. */
const LIVE = {
  checked_at: "2026-09-09T05:00:00Z",
  report_id: "KL-TVM-DEMO-001",
  demo: true,
  generated_at: null,
  economics_version: "0.1.0",
  engine_economics_version: "0.5.0",
  model_version: "synthetic_v0",
  renderer_version: null,
  site_facts: 16,
  cpo_rows: 4,
  ledger_rows: 11,
  sections: SECTIONS.map((s, i) => ({
    n: i + 1,
    id: s.id,
    title: s.title,
    dropped: s.id === "ledger" ? ["the engine's own assumption ledger"] : [],
  })),
  archive: {
    table_exists: false,
    archived: false,
    renderer_version: null,
    pages: null,
    byte_size: null,
    rendered_at: null,
  },
};

function renderPanel(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response)),
  );
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ReportBuild />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the live half of the panel", () => {
  it("says a payload behind the engine is OLD, not unbuilt", async () => {
    // The two read identically on the page - a section reporting a gap - and
    // they have opposite fixes. Regenerating the demo closes one of them and
    // does nothing at all for the other.
    renderPanel(LIVE);
    expect(await screen.findByText(/economics 0.1.0 and the engine/)).toBeTruthy();
    expect(screen.getByText(/regenerated in place/)).toBeTruthy();
  });

  it("reports a missing report_pdfs as an answer rather than a failure", async () => {
    renderPanel(LIVE);
    expect(await screen.findByText(/migration 0013 not applied/)).toBeTruthy();
    expect(screen.getByText("nothing archived yet")).toBeTruthy();
  });

  it("renders the record when the endpoint is unreachable", async () => {
    // The hand-kept half is the part someone opens this page for after
    // something has broken. It must not depend on the API answering.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve({ ok: false, status: 500 } as Response)),
    );
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <ReportBuild />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(await screen.findByText(/Could not read the document record/)).toBeTruthy();
    expect(screen.getByText(/06 · Operator comparison/)).toBeTruthy();
    expect(screen.getByText(/break-inside: avoid is INERT/)).toBeTruthy();
  });
});
