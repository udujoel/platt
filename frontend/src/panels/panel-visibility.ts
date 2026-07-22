import type { RailPanel } from "./IconRail";

/** Rail click: opens the clicked panel, or closes it if it's already active. */
export function toggleActivePanel(current: RailPanel | null, panel: RailPanel): RailPanel | null {
  return current === panel ? null : panel;
}

/**
 * A panel's own close control only clears its own panel. If a different
 * panel has since become active (e.g. the operator switched panels while
 * this one was still animating out), a stale close must not clobber it.
 */
export function closeActivePanel(current: RailPanel | null, panel: RailPanel): RailPanel | null {
  return current === panel ? null : current;
}
