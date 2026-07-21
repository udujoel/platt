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
  it("fades in with no fade-out clip on first mount", () => {
    expect(selectCrossfade(null, "idle")).toEqual({
      fadeOutClip: null,
      fadeInClip: "idle",
      fadeOutSeconds: 0.3,
      fadeInSeconds: 0.3,
    });
  });

  it("crossfades over 0.3s per PRD 5.3 when the mapped clip changes", () => {
    expect(selectCrossfade("idle", "working")).toEqual({
      fadeOutClip: "idle",
      fadeInClip: "sit_type",
      fadeOutSeconds: 0.3,
      fadeInSeconds: 0.3,
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
