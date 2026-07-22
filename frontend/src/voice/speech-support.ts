export type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

export type SpeechWindow = {
  SpeechRecognition?: SpeechRecognitionCtor;
  webkitSpeechRecognition?: SpeechRecognitionCtor;
  speechSynthesis?: unknown;
  SpeechSynthesisUtterance?: unknown;
};

/** Chrome/Edge ship it prefixed, Safari/Firefox may not ship it at all — try both, degrade to null. */
export function getSpeechRecognitionCtor(win: SpeechWindow | undefined): SpeechRecognitionCtor | null {
  return win?.SpeechRecognition ?? win?.webkitSpeechRecognition ?? null;
}

export function isSpeechSynthesisSupported(win: SpeechWindow | undefined): boolean {
  return typeof win?.speechSynthesis === "object" && win.speechSynthesis !== null && typeof win?.SpeechSynthesisUtterance === "function";
}
