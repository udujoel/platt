/** A synthetic "the utterance said a word here" pulse, timed relative to utterance start. */
export type BoundaryPulse = { elapsedMs: number };

export const PULSE_PEAK_AMPLITUDE = 1;
export const PULSE_DECAY_MS = 180;

/**
 * `speechSynthesis` exposes no audio waveform, so mouth movement is approximated from
 * `SpeechSynthesisUtterance` `boundary` events (one per spoken word): each pulses the amplitude
 * to its peak, then linearly decays over `decayMs`. Sampled once per animation frame with the
 * elapsed time since the utterance started, this gives a jaw that opens on each word and closes
 * between them without ever needing real audio analysis.
 */
export function amplitudeAtElapsed(pulses: BoundaryPulse[], elapsedMs: number, decayMs: number = PULSE_DECAY_MS): number {
  let amplitude = 0;
  for (const pulse of pulses) {
    if (pulse.elapsedMs > elapsedMs) continue;
    const age = elapsedMs - pulse.elapsedMs;
    if (age >= decayMs) continue;
    const value = PULSE_PEAK_AMPLITUDE * (1 - age / decayMs);
    if (value > amplitude) amplitude = value;
  }
  return amplitude;
}
