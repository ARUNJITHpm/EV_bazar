import { describe, expect, it } from "vitest";

import { loadState, placeName, saveState, toBody } from "./state";

const PIN = { lat: 8.5695, lng: 76.873 };

describe("toBody", () => {
  it("maps skip and unasked alike to null, so the backend echoes the default", () => {
    const body = toBody(PIN, { connection: "skip", transformer: "skip" });
    expect(body.existing_connection).toBeNull();
    expect(body.transformer_on_site).toBeNull();
    expect(body.land_owned).toBeNull();
    expect(body.intent).toBeNull();
    expect(body.sanctioned_kva).toBeNull();
  });

  it("carries real answers through, including a skipped kVA after a yes", () => {
    const body = toBody(PIN, {
      connection: "yes",
      kva: 150,
      transformer: "no",
      land: "own",
      intent: "income",
    });
    expect(body.existing_connection).toBe(true);
    expect(body.sanctioned_kva).toBe(150);
    expect(body.transformer_on_site).toBe(false);
    expect(body.land_owned).toBe(true);
    expect(body.intent).toBe("earn from land I own");

    // "Yes there is a connection, but I don't know the load" must not
    // invent a number.
    const skipped = toBody(PIN, { connection: "yes", kva: "skip" });
    expect(skipped.existing_connection).toBe(true);
    expect(skipped.sanctioned_kva).toBeNull();
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
    saveState({ pin: PIN, answers: { land: "lease" } });
    expect(loadState().answers.land).toBe("lease");
    expect(loadState().pin).toEqual(PIN);

    sessionStorage.setItem("cw.assessment", "{not json");
    expect(loadState()).toEqual({ answers: {} });
  });
});
