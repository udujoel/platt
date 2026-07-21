export const BUBBLE_MAX_CHARS = 220;
export const BUBBLE_HIDE_DELAY_MS = 4000;

/** Truncates streaming speech to the tail per PRD 5.3 ("truncates past around 220 characters"). */
export function truncateBubbleText(text: string, maxChars: number = BUBBLE_MAX_CHARS): string {
  if (text.length <= maxChars) return text;
  return text.slice(-maxChars);
}

/** Bubble shows while talking with content, then lingers up to BUBBLE_HIDE_DELAY_MS after the message completes. */
export function isBubbleVisible({
  state,
  hasSpeech,
  msSinceMessageComplete,
}: {
  state: string;
  hasSpeech: boolean;
  msSinceMessageComplete: number | null;
}): boolean {
  if (!hasSpeech) return false;
  if (state === "talking") return true;
  if (msSinceMessageComplete === null) return false;
  return msSinceMessageComplete < BUBBLE_HIDE_DELAY_MS;
}
