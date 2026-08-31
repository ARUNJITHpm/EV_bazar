import { describe, expect, it } from "vitest";

import { loadState, placeName, saveState, toBody } from "./state";

const PIN = { lat: 8.5695, lng: 76.873 };

describe("toBody", () => {
  it("maps skip and unasked alike to null, so the backend echoes the default", () => {
    const body = toBody(PIN, { transformerNear: "skip", transformerKva: "skip" });
    expect(body.transformer_kva).toBeNull();
    expect(body.transformer_distance_m).toBeNull();
    expect(body.space).toBeNull();
    expect(body.intent).toBeNull();
  });

  it("carries real answers through, including a skipped size after a yes", () => {
    const body = toBody(PIN, {
      transformerNear: "yes",
      transformerDistanceM: 120,
      transformerKva: 250,
      space: "large",
      intent: "income",
    });
    expect(body.transformer_distance_m).toBe(120);
    expect(body.transformer_kva).toBe(250);
    expect(body.space).toBe("large");
    expect(body.intent).toBe("earn from land I own");

    // "Yes there is a transformer, but I don't know its size" must not
    // invent a number.
    const skipped = toBody(PIN, { transformerNear: "yes", transformerKva: "skip" });
    expect(skipped.transformer_kva).toBeNull();
  });
});

describe("placeName", () => {
  it("stops the reference layer's caps from shouting at the customer", () => {
    expect(placeName("Thiruvananthapuram", "KERALA")).toBe("Thiruvananthapuram, Kerala");
    expect(placeName("Coimbatore", "TAMIL NADU")).toBe("Coimbatore, Tamil Nadu");
    expect(placeName("Dakshina Kannada", "JAMMU AND KASHMIR")).toBe(
      "Dakshina Kannada, Jammu And Kashmir",
    );
    expect(placeName(null, null)).toBe("");
  });
});

describe("session persistence", () => {
  it("round-trips the state and survives garbage", () => {
    saveState({ pin: PIN, answers: { space: "medium" } });
    expect(loadState().answers.space).toBe("medium");
    expect(loadState().pin).toEqual(PIN);

    sessionStorage.setItem("cw.assessment", "{not json");
    expect(loadState()).toEqual({ answers: {} });
  });
});
