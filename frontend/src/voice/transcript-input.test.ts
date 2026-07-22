import { describe, expect, it } from "vitest";

import { applyTranscriptEvent } from "./transcript-input";

describe("applyTranscriptEvent", () => {
  it("mirrors interim transcripts into the draft without sending", () => {
    const result = applyTranscriptEvent("", { transcript: "deploy the", isFinal: false });
    expect(result).toEqual({ draft: "deploy the", shouldSend: false });
  });

  it("sends once a final transcript has real content", () => {
    const result = applyTranscriptEvent("deploy the", { transcript: "deploy the storage account", isFinal: true });
    expect(result).toEqual({ draft: "deploy the storage account", shouldSend: true });
  });

  it("does not send an empty final transcript", () => {
    const result = applyTranscriptEvent("hello", { transcript: "", isFinal: true });
    expect(result).toEqual({ draft: "hello", shouldSend: false });
  });

  it("does not send a whitespace-only final transcript", () => {
    const result = applyTranscriptEvent("hello", { transcript: "   ", isFinal: true });
    expect(result).toEqual({ draft: "hello", shouldSend: false });
  });

  it("keeps the prior draft when a final result carries no content", () => {
    const result = applyTranscriptEvent("existing text", { transcript: "  ", isFinal: true });
    expect(result.draft).toBe("existing text");
  });
});
