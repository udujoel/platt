import React from "react";
import { applyTranscriptEvent } from "./transcript-input";
import { getSpeechRecognitionCtor } from "./speech-support";

/**
 * Thin React wrapper around the Web Speech `SpeechRecognition` API (mic button, PRD F8). All the
 * decision logic (what to show, when to auto-send) lives in the pure `transcript-input` module
 * and is unit tested there; this hook only owns the imperative browser object and its lifecycle.
 */
export function useSpeechRecognition({
  getDraft,
  onDraftChange,
  onAutoSend,
}: {
  /** Reads the composer's current draft so starting recognition doesn't clobber text already typed. */
  getDraft: () => string;
  onDraftChange: (draft: string) => void;
  onAutoSend: (text: string) => void;
}) {
  const ctor = React.useMemo(() => getSpeechRecognitionCtor(typeof window === "undefined" ? undefined : window), []);
  const supported = ctor !== null;

  const [listening, setListening] = React.useState(false);
  const recognitionRef = React.useRef<SpeechRecognitionLike | null>(null);
  const draftRef = React.useRef("");

  const stop = React.useCallback(() => {
    recognitionRef.current?.stop();
  }, []);

  const start = React.useCallback(() => {
    if (!ctor || listening) return;

    const recognition = new ctor();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event) => {
      const result = event.results[event.results.length - 1];
      const transcript = result?.[0]?.transcript ?? "";
      const decision = applyTranscriptEvent(draftRef.current, { transcript, isFinal: result?.isFinal ?? false });
      draftRef.current = decision.draft;
      onDraftChange(decision.draft);
      if (decision.shouldSend) onAutoSend(decision.draft);
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = () => setListening(false);

    recognitionRef.current = recognition;
    draftRef.current = getDraft();
    setListening(true);
    recognition.start();
  }, [ctor, getDraft, listening, onAutoSend, onDraftChange]);

  const toggle = React.useCallback(() => {
    if (listening) stop();
    else start();
  }, [listening, start, stop]);

  React.useEffect(() => {
    return () => recognitionRef.current?.abort();
  }, []);

  return { supported, listening, toggle };
}
