import type { CharacterHandle, CrossfadePlan, PlattClipName } from "./types";

/**
 * Bridges the stable `CharacterHandle` handed to `PlattController` to whichever underlying
 * character instance (`PlattCharacterGLB` or `ProceduralPlatt`) is currently mounted. Suspense
 * (and `CharacterErrorBoundary`) swap in a *fresh* underlying instance whenever the glb resolves
 * or fails to load — each fresh instance starts blank and knows nothing about a crossfade that
 * was already mid-flight. This relay remembers the last `CrossfadePlan` it was asked to run and
 * replays it onto whichever instance attaches next, so a swap never drops the active animation.
 */
export function createCharacterHandleRelay(initialClip: PlattClipName) {
  let active: CharacterHandle | null = null;
  let lastPlan: CrossfadePlan | null = null;
  let lastClip: PlattClipName = initialClip;

  const handle: CharacterHandle = {
    get currentClip() {
      return active?.currentClip ?? lastClip;
    },
    playClip(plan: CrossfadePlan) {
      lastPlan = plan;
      lastClip = plan.fadeInClip;
      active?.playClip(plan);
    },
  };

  function attach(next: CharacterHandle | null) {
    active = next;
    if (next && lastPlan) {
      next.playClip(lastPlan);
    }
  }

  return { handle, attach };
}
