import { describe, expect, it } from "vitest";

import { getThreeStagePose } from "./three-stage-pose";

describe("getThreeStagePose", () => {
  it("gives each steady state a distinct, intentional pose", () => {
    expect(getThreeStagePose("idle", 0)).toMatchObject({ x: 0, y: 1.05, headTilt: 0, leftArm: 0.28, rightArm: -0.28 });
    expect(getThreeStagePose("listening", 0)).toMatchObject({ headTilt: -0.1, leftArm: 0.12, rightArm: -0.12 });
    expect(getThreeStagePose("working", 0)).toMatchObject({ x: 1.55, headTilt: 0.1, leftArm: 0.8, rightArm: -0.8 });
    expect(getThreeStagePose("awaiting_approval", 0)).toMatchObject({ x: -1.55, leftArm: 1.1, rightArm: -1.25 });
  });

  it("keeps the animated state poses driven by elapsed time", () => {
    expect(getThreeStagePose("thinking", Math.PI / 4).x).toBeCloseTo(0.3);
    expect(getThreeStagePose("working", Math.PI / 36).leftArm).toBeCloseTo(0.94);
    expect(getThreeStagePose("talking", Math.PI / 16).rightArm).toBeCloseTo(-0.95);
    expect(getThreeStagePose("celebrating", Math.PI / 16).y).toBeCloseTo(1.39);
    expect(getThreeStagePose("concerned", Math.PI / 44).bodyLean).toBeCloseTo(0.06);
  });
});
