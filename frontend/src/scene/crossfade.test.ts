import { describe, expect, it } from "vitest";

import { clipForState, selectCrossfade } from "./crossfade";

describe("clipForState", () => {
  it("maps every event state to a Mixamo clip name from PRD 5.1", () => {
    expect(clipForState("idle")).toBe("idle");
    expect(clipForState("thinking")).toBe("think");
    expect(clipForState("working")).toBe("sit_type");
    expect(clipForState("talking")).toBe("talk");
    expect(clipForState("celebrating")).toBe("celebrate");
    expect(clipForState("concerned")).toBe("dejected");
  });
});

describe("selectCrossfade", () => {
  it("fades in on the target state's tuned duration with no fade-out clip on first mount", () => {
    expect(selectCrossfade(null, "idle")).toEqual({
      fadeOutClip: null,
      fadeInClip: "idle",
      fadeOutSeconds: 0,
      fadeInSeconds: 0.4,
    });
  });

  it("crossfades per PRD 5.3 when the mapped clip changes, each side on its own state's duration", () => {
    expect(selectCrossfade("idle", "working")).toEqual({
      fadeOutClip: "idle",
      fadeInClip: "sit_type",
      fadeOutSeconds: 0.4,
      fadeInSeconds: 0.45,
    });
  });

  it("fades in celebrating fast regardless of how slowly the outgoing state prefers to fade out", () => {
    expect(selectCrossfade("working", "celebrating")).toEqual({
      fadeOutClip: "sit_type",
      fadeInClip: "celebrate",
      fadeOutSeconds: 0.45,
      fadeInSeconds: 0.15,
    });
  });

  it("is a no-op when two states share the same clip", () => {
    expect(selectCrossfade("listening", "awaiting_approval")).toEqual({
      fadeOutClip: null,
      fadeInClip: "idle_breathe",
      fadeOutSeconds: 0,
      fadeInSeconds: 0,
    });
  });
});
