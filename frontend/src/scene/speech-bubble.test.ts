import { describe, expect, it } from "vitest";

import { BUBBLE_HIDE_DELAY_MS, BUBBLE_MAX_CHARS, isBubbleVisible, truncateBubbleText } from "./speech-bubble";

describe("truncateBubbleText", () => {
  it("keeps short text untouched", () => {
    expect(truncateBubbleText("hello")).toBe("hello");
  });

  it("truncates to the tail past the max length, per PRD 5.3 (~220 chars)", () => {
    const text = "x".repeat(BUBBLE_MAX_CHARS + 50) + "END";
    const truncated = truncateBubbleText(text);
    expect(truncated).toHaveLength(BUBBLE_MAX_CHARS);
    expect(truncated.endsWith("END")).toBe(true);
  });
});

describe("isBubbleVisible", () => {
  it("is hidden with no speech regardless of state", () => {
    expect(isBubbleVisible({ state: "talking", hasSpeech: false, msSinceMessageComplete: null })).toBe(false);
  });

  it("stays visible while talking", () => {
    expect(isBubbleVisible({ state: "talking", hasSpeech: true, msSinceMessageComplete: null })).toBe(true);
  });

  it("lingers up to the hide delay after the message completes", () => {
    expect(isBubbleVisible({ state: "idle", hasSpeech: true, msSinceMessageComplete: BUBBLE_HIDE_DELAY_MS - 1 })).toBe(true);
    expect(isBubbleVisible({ state: "idle", hasSpeech: true, msSinceMessageComplete: BUBBLE_HIDE_DELAY_MS })).toBe(false);
  });

  it("is hidden once not talking with no completion timestamp yet", () => {
    expect(isBubbleVisible({ state: "idle", hasSpeech: true, msSinceMessageComplete: null })).toBe(false);
  });
});
