import React from "react";
import { Mic, MicOff } from "lucide-react";
import { useSpeechRecognition } from "./use-speech-recognition";

/**
 * Mic toggle for the chat composer (PRD F8): transcribes speech into the given draft setter and
 * auto-sends on a final result. Renders nothing when the browser has no `SpeechRecognition` —
 * graceful degradation per the spec, no broken button to click.
 */
export function MicButton({
  disabled,
  onDraftChange,
  onAutoSend,
}: {
  disabled?: boolean;
  onDraftChange: (draft: string) => void;
  onAutoSend: (text: string) => void;
}) {
  const { supported, listening, toggle } = useSpeechRecognition({ onDraftChange, onAutoSend });

  if (!supported) return null;

  return (
    <button
      type="button"
      className={`micButton ${listening ? "listening" : ""}`}
      aria-label={listening ? "Stop voice input" : "Start voice input"}
      aria-pressed={listening}
      title={listening ? "Stop voice input" : "Speak your message"}
      disabled={disabled}
      onClick={toggle}
    >
      {listening ? <MicOff size={18} aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
    </button>
  );
}
