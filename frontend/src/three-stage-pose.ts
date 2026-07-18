export type ThreeStageState =
  | "idle"
  | "listening"
  | "thinking"
  | "working"
  | "talking"
  | "awaiting_approval"
  | "celebrating"
  | "concerned";

export type ThreeStagePose = {
  bodyLean: number;
  headTilt: number;
  leftArm: number;
  rightArm: number;
  x: number;
  y: number;
};

const BASE_HEIGHT = 1.05;

/** Returns the current 3D rig pose for the truthful agent event state. */
export function getThreeStagePose(state: ThreeStageState, elapsedSeconds: number): ThreeStagePose {
  switch (state) {
    case "listening":
      return { x: 0, y: BASE_HEIGHT, bodyLean: 0.02, headTilt: -0.1, leftArm: 0.12, rightArm: -0.12 };
    case "thinking":
      return {
        x: Math.sin(elapsedSeconds * 2) * 0.3,
        y: BASE_HEIGHT,
        bodyLean: Math.sin(elapsedSeconds * 4) * 0.035,
        headTilt: 0.08,
        leftArm: 0.18,
        rightArm: -0.18,
      };
    case "working": {
      const typingOffset = Math.sin(elapsedSeconds * 18) * 0.14;
      return { x: 1.55, y: BASE_HEIGHT, bodyLean: 0.04, headTilt: 0.1, leftArm: 0.8 + typingOffset, rightArm: -0.8 - typingOffset };
    }
    case "talking":
      return {
        x: 0,
        y: BASE_HEIGHT,
        bodyLean: 0,
        headTilt: Math.sin(elapsedSeconds * 8) * 0.04,
        leftArm: 0.28,
        rightArm: -0.72 - Math.sin(elapsedSeconds * 8) * 0.23,
      };
    case "awaiting_approval":
      return { x: -1.55, y: BASE_HEIGHT, bodyLean: -0.02, headTilt: -0.04, leftArm: 1.1, rightArm: -1.25 };
    case "celebrating":
      return {
        x: 0,
        y: BASE_HEIGHT + Math.abs(Math.sin(elapsedSeconds * 8)) * 0.34,
        bodyLean: 0,
        headTilt: 0,
        leftArm: 2.08 + Math.sin(elapsedSeconds * 10) * 0.1,
        rightArm: -2.08 - Math.sin(elapsedSeconds * 10) * 0.1,
      };
    case "concerned":
      return { x: 0, y: BASE_HEIGHT, bodyLean: Math.sin(elapsedSeconds * 22) * 0.06, headTilt: 0.05, leftArm: 0.05, rightArm: -0.05 };
    case "idle":
      return { x: 0, y: BASE_HEIGHT, bodyLean: 0, headTilt: 0, leftArm: 0.28, rightArm: -0.28 };
  }
}
