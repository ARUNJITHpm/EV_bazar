import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GridConditions } from "./GridConditions";
import fixture from "./fixtures/part13-public-context.json";
import type { components } from "../../api/schema";

const context: components["schemas"]["PublicContextPayload"] = {
  ...fixture,
  version: "public_context_v1",
};

describe("stored grid confirmation condition", () => {
  it("leaves reports without public context unchanged", () => {
    const { container } = render(<GridConditions payload={{}} />);
    expect(container.innerHTML).toBe("");
  });

  it("prints the stored kVA threshold and the mapped-capacity limitation", () => {
    const { container } = render(<GridConditions payload={{ public_context: context }} />);
    expect(container.textContent).toContain(context.grid_conditions![0]);
    expect(screen.getByText(/Mapped proximity does not confirm spare capacity/)).toBeTruthy();
  });

  it("prints no new condition when capacity has already been verified", () => {
    const { container } = render(
      <GridConditions payload={{ public_context: { ...context, grid_conditions: [] } }} />,
    );
    expect(container.innerHTML).toBe("");
  });
});
