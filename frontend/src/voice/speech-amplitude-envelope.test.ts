import { describe, expect, it } from "vitest";

import { PULSE_DECAY_MS, amplitudeAtElapsed } from "./speech-amplitude-envelope";

describe("amplitudeAtElapsed", () => {
  it("is silent with no pulses", () => {
    expect(amplitudeAtElapsed([], 500)).toBe(0);
  });

  it("is silent before the first pulse", () => {
    expect(amplitudeAtElapsed([{ elapsedMs: 200 }], 100)).toBe(0);
  });

  it("peaks exactly at a pulse", () => {
    expect(amplitudeAtElapsed([{ elapsedMs: 200 }], 200)).toBe(1);
  });

  it("decays linearly toward zero over the decay window", () => {
    const half = amplitudeAtElapsed([{ elapsedMs: 0 }], PULSE_DECAY_MS / 2);
    expect(half).toBeCloseTo(0.5, 5);
  });

  it("is silent once the decay window has fully elapsed", () => {
    expect(amplitudeAtElapsed([{ elapsedMs: 0 }], PULSE_DECAY_MS)).toBe(0);
    expect(amplitudeAtElapsed([{ elapsedMs: 0 }], PULSE_DECAY_MS + 500)).toBe(0);
  });

  it("ignores pulses that haven't happened yet", () => {
    expect(amplitudeAtElapsed([{ elapsedMs: 0 }, { elapsedMs: 9999 }], 10)).toBeGreaterThan(0);
  });

  it("takes the loudest of several overlapping pulses", () => {
    const amplitude = amplitudeAtElapsed([{ elapsedMs: 0 }, { elapsedMs: 50 }], 60);
    const soleLaterPulse = amplitudeAtElapsed([{ elapsedMs: 50 }], 60);
    expect(amplitude).toBeCloseTo(soleLaterPulse, 5);
  });

  it("respects a custom decay window", () => {
    expect(amplitudeAtElapsed([{ elapsedMs: 0 }], 50, 100)).toBeCloseTo(0.5, 5);
  });
});
