import { describe, expect, it } from "vitest";

import { JAW_MAX_ROTATION, JAW_REST_ROTATION, amplitudeToJawRotation } from "./amplitude-jaw";

describe("amplitudeToJawRotation", () => {
  it("maps silence to the rest rotation", () => {
    expect(amplitudeToJawRotation(0)).toBe(JAW_REST_ROTATION);
  });

  it("maps full amplitude to the max rotation", () => {
    expect(amplitudeToJawRotation(1)).toBe(JAW_MAX_ROTATION);
  });

  it("eases quiet amplitudes open further than a linear map would, so quiet syllables still read", () => {
    const eased = amplitudeToJawRotation(0.25);
    expect(eased).toBeGreaterThan(JAW_MAX_ROTATION * 0.25);
    expect(eased).toBeCloseTo(JAW_MAX_ROTATION * 0.25 ** 0.6, 5);
  });

  it("clamps amplitudes below zero", () => {
    expect(amplitudeToJawRotation(-3)).toBe(JAW_REST_ROTATION);
  });

  it("clamps amplitudes above one", () => {
    expect(amplitudeToJawRotation(3)).toBe(JAW_MAX_ROTATION);
  });

  it("honors a custom max rotation", () => {
    expect(amplitudeToJawRotation(1, 0.2)).toBe(0.2);
  });

  it("honors a custom response curve", () => {
    expect(amplitudeToJawRotation(0.5, JAW_MAX_ROTATION, 1)).toBeCloseTo(JAW_MAX_ROTATION / 2, 5);
  });
});
