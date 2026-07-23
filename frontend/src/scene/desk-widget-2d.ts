import type { ThreeStageState } from "../three-stage-pose";

/** Pure state -> visual mapping for the 2D fallback (`PlattDeskWidget`'s reduced-motion/no-WebGL path). */
export function deskFallbackMonitorColor(state: ThreeStageState): string {
  if (state === "concerned") return "#f87171";
  if (state === "working" || state === "thinking") return "#ffb454";
  return "#2dd4bf";
}

/** Short status word shown under the 2D fallback's mini monitor, mirroring the state names 1:1. */
export function deskFallbackStatusLabel(state: ThreeStageState): string {
  return state.replace(/_/g, " ");
}
