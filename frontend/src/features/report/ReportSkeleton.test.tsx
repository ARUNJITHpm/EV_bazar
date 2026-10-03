import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SECTIONS } from "../console/ReportBuild";
import { REPORT_OUTLINE, ReportSkeleton } from "./ReportSkeleton";

describe("ReportSkeleton", () => {
  it("outlines exactly the twelve sections the report renders, in order", () => {
    expect(REPORT_OUTLINE.map((s) => `${s.n} ${s.title}`)).toEqual(
      SECTIONS.map((s) => `${s.n} ${s.title}`),
    );
  });

  it("never carries the flag the PDF path waits on", () => {
    const { container } = render(<ReportSkeleton line="Your land, our homework." />);
    expect(container.querySelector("[data-report-ready]")).toBeNull();
    expect(screen.getByRole("status").textContent).toContain("Fetching the stored report");
  });
});
