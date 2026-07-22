import type { PlattState } from "../backend-events";

export type TtsSpeakInput = {
  state: PlattState;
  muted: boolean;
  text: string;
  messageId: string;
  lastSpokenMessageId: string | null;
};

/**
 * Speak a given assistant message at most once: only while Platt is actually `talking`, unmuted,
 * and there's real text — and only the first time we see this message id, so a re-render (e.g.
 * more streamed tokens arriving) doesn't restart the utterance from the top each time.
 */
export function shouldStartSpeaking(input: TtsSpeakInput): boolean {
  if (input.muted) return false;
  if (input.state !== "talking") return false;
  if (!input.text.trim()) return false;
  return input.messageId !== input.lastSpokenMessageId;
}

export type TtsCancelInput = {
  state: PlattState;
  muted: boolean;
  isSpeaking: boolean;
};

/**
 * Interrupt in-flight speech the moment it's no longer appropriate: the user muted mid-utterance,
 * or Platt moved on to a different state (a new message started, or the turn ended).
 */
export function shouldCancelSpeaking(input: TtsCancelInput): boolean {
  if (!input.isSpeaking) return false;
  return input.muted || input.state !== "talking";
}
