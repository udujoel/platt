/** Rest and fully-open jaw rotation (radians) applied to the glb jaw bone / procedural jaw mesh. */
export const JAW_REST_ROTATION = 0;
export const JAW_MAX_ROTATION = 0.42;

/**
 * Pure amplitude (0..1) -> jaw rotation (radians) mapping, per PRD F8 ("mouth movement
 * approximated by amplitude driven jaw rotation"). Shared by `PlattCharacterGLB` and
 * `ProceduralPlatt` so both rigs move the same way for the same amplitude signal.
 */
export function amplitudeToJawRotation(amplitude: number, maxRotation: number = JAW_MAX_ROTATION): number {
  const clamped = Math.min(1, Math.max(0, amplitude));
  return JAW_REST_ROTATION + clamped * (maxRotation - JAW_REST_ROTATION);
}
