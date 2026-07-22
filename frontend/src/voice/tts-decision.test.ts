import { describe, expect, it } from "vitest";

import { shouldCancelSpeaking, shouldStartSpeaking } from "./tts-decision";

describe("shouldStartSpeaking", () => {
  const base = { state: "talking" as const, muted: false, text: "hello there", messageId: "m1", lastSpokenMessageId: null };

  it("starts for a fresh talking message when unmuted", () => {
    expect(shouldStartSpeaking(base)).toBe(true);
  });

  it("does not start when muted", () => {
    expect(shouldStartSpeaking({ ...base, muted: true })).toBe(false);
  });

  it("does not start outside the talking state", () => {
    expect(shouldStartSpeaking({ ...base, state: "thinking" })).toBe(false);
  });

  it("does not start with empty text", () => {
    expect(shouldStartSpeaking({ ...base, text: "   " })).toBe(false);
  });

  it("does not restart a message it has already spoken", () => {
    expect(shouldStartSpeaking({ ...base, lastSpokenMessageId: "m1" })).toBe(false);
  });

  it("starts again once a new message id arrives", () => {
    expect(shouldStartSpeaking({ ...base, messageId: "m2", lastSpokenMessageId: "m1" })).toBe(true);
  });
});

describe("shouldCancelSpeaking", () => {
  it("does nothing when nothing is speaking", () => {
    expect(shouldCancelSpeaking({ state: "talking", muted: false, isSpeaking: false })).toBe(false);
  });

  it("cancels when muted mid-utterance", () => {
    expect(shouldCancelSpeaking({ state: "talking", muted: true, isSpeaking: true })).toBe(true);
  });

  it("cancels when the state moves on from talking", () => {
    expect(shouldCancelSpeaking({ state: "idle", muted: false, isSpeaking: true })).toBe(true);
  });

  it("keeps speaking while still talking and unmuted", () => {
    expect(shouldCancelSpeaking({ state: "talking", muted: false, isSpeaking: true })).toBe(false);
  });
});
