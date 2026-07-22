import { describe, expect, it, vi } from "vitest";

import { startRecognitionSafely } from "./start-recognition";

describe("startRecognitionSafely", () => {
  it("returns true when start() succeeds", () => {
    const recognition = { start: vi.fn() };
    expect(startRecognitionSafely(recognition)).toBe(true);
    expect(recognition.start).toHaveBeenCalledOnce();
  });

  it("returns false instead of throwing when start() throws synchronously", () => {
    const recognition = {
      start: vi.fn(() => {
        throw new DOMException("already started", "InvalidStateError");
      }),
    };

    expect(() => startRecognitionSafely(recognition)).not.toThrow();
    expect(startRecognitionSafely(recognition)).toBe(false);
  });
});
