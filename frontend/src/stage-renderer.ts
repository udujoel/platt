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

/** Preserves the accessible 2D stage if the active WebGL context becomes unusable. */
export function createWebGLContextLossHandler(onFallback: () => void) {
  return (event: Pick<Event, "preventDefault">) => {
    event.preventDefault();
    onFallback();
  };
}
