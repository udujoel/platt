export type StageRenderer = "three" | "fallback";

export function selectStageRenderer({
  prefersReducedMotion,
  supportsWebGL,
}: {
  prefersReducedMotion: boolean;
  supportsWebGL: boolean;
}): StageRenderer {
  return prefersReducedMotion || !supportsWebGL ? "fallback" : "three";
}
