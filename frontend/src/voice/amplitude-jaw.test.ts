import { describe, expect, it } from "vitest";

import { JAW_MAX_ROTATION, JAW_REST_ROTATION, amplitudeToJawRotation } from "./amplitude-jaw";

describe("amplitudeToJawRotation", () => {
  it("maps silence to the rest rotation", () => {
    expect(amplitudeToJawRotation(0)).toBe(JAW_REST_ROTATION);
  });

  it("maps full amplitude to the max rotation", () => {
    expect(amplitudeToJawRotation(1)).toBe(JAW_MAX_ROTATION);
  });

  it("interpolates linearly between rest and max", () => {
    expect(amplitudeToJawRotation(0.5)).toBeCloseTo(JAW_MAX_ROTATION / 2, 5);
  });

  it("clamps amplitudes below zero", () => {
    expect(amplitudeToJawRotation(-3)).toBe(JAW_REST_ROTATION);
  });

  it("clamps amplitudes above one", () => {
    expect(amplitudeToJawRotation(3)).toBe(JAW_MAX_ROTATION);
  });

  it("honors a custom max rotation", () => {
    expect(amplitudeToJawRotation(1, 0.2)).toBe(0.2);
    expect(amplitudeToJawRotation(0.5, 0.2)).toBeCloseTo(0.1, 5);
  });
});
