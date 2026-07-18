import { describe, expect, it } from "vitest";

import { selectStageRenderer } from "./stage-renderer";

describe("selectStageRenderer", () => {
  it("uses the 3D scene when WebGL is available and motion is allowed", () => {
    expect(selectStageRenderer({ supportsWebGL: true, prefersReducedMotion: false })).toBe("three");
  });

  it("keeps the 2D scene for reduced motion or missing WebGL", () => {
    expect(selectStageRenderer({ supportsWebGL: false, prefersReducedMotion: false })).toBe("fallback");
    expect(selectStageRenderer({ supportsWebGL: true, prefersReducedMotion: true })).toBe("fallback");
  });
});
