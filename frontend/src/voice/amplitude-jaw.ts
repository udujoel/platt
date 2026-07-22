/** Rest and fully-open jaw rotation (radians) applied to the glb jaw bone / procedural jaw mesh. */
export const JAW_REST_ROTATION = 0;
export const JAW_MAX_ROTATION = 0.42;
/** Perceptual response curve: <1 opens the jaw more at low amplitude, mirroring how speech reads
 * as mouth movement even on quiet syllables rather than only snapping open on loud ones. */
export const JAW_RESPONSE_CURVE = 0.6;

/**
 * Pure amplitude (0..1) -> jaw rotation (radians) mapping, per PRD F8 ("mouth movement
 * approximated by amplitude driven jaw rotation"). Shared by `PlattCharacterGLB` and
 * `ProceduralPlatt` so both rigs move the same way for the same amplitude signal.
 *
 * A straight linear map reads as buzzy/mechanical because most speech amplitude sits in the
 * low-to-mid range with only occasional loud peaks, so a linear jaw barely opens most of the
 * time and then snaps wide on peaks. Easing with `amplitude ** JAW_RESPONSE_CURVE` (< 1) lifts
 * the low end so quieter syllables still read as visible mouth movement, while 0 and 1 stay
 * pinned to fully closed / fully open.
 */
export function amplitudeToJawRotation(
  amplitude: number,
  maxRotation: number = JAW_MAX_ROTATION,
  responseCurve: number = JAW_RESPONSE_CURVE,
): number {
  if (!Number.isFinite(responseCurve) || responseCurve <= 0) {
    // A zero/negative/non-finite exponent breaks the 0..1 easing (e.g. 0 ** 0 === 1 opens the
    // jaw fully on silence), so reject it instead of silently mis-mapping amplitude to rotation.
    throw new RangeError("responseCurve must be a finite positive number");
  }
  const clamped = Math.min(1, Math.max(0, amplitude));
  const eased = clamped ** responseCurve;
  return JAW_REST_ROTATION + eased * (maxRotation - JAW_REST_ROTATION);
}
