export type SpeechTranscriptEvent = {
  transcript: string;
  isFinal: boolean;
};

export type TranscriptDecision = {
  /** Text the chat input should show right now (interim results included, for live feedback). */
  draft: string;
  /** True once a non-empty final transcript has arrived and the message should auto-send. */
  shouldSend: boolean;
};

/**
 * Maps one `SpeechRecognition` result onto the chat composer: interim results just update the
 * draft live so the user sees what's being heard; a final result with real content auto-sends.
 * A final result that transcribed to nothing (silence, unrecognized speech) leaves the draft
 * alone rather than clearing text the user may have typed before pressing the mic button.
 */
export function applyTranscriptEvent(previousDraft: string, event: SpeechTranscriptEvent): TranscriptDecision {
  const trimmed = event.transcript.trim();
  if (event.isFinal && !trimmed) {
    return { draft: previousDraft, shouldSend: false };
  }
  return { draft: event.transcript, shouldSend: event.isFinal && trimmed.length > 0 };
}
