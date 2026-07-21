import React from "react";
import { CharacterErrorBoundary } from "./CharacterErrorBoundary";
import { PlattCharacterGLB } from "./PlattCharacterGLB";
import { ProceduralPlatt } from "./ProceduralPlatt";
import type { CharacterHandle, PlattCharacterProps } from "./types";

/**
 * Selects the glb-driven `platt.glb` character (T-D1, `PlattCharacterGLB`) when it loads
 * successfully, falling back to the procedural rig (`ProceduralPlatt`) while it loads and if
 * the asset is missing or fails to parse — see `ASSETS.md` for how to produce `platt.glb`.
 * `PlattController` only ever renders this component and only ever needs the `CharacterHandle`
 * contract, so it doesn't need to know (or change) which rig is actually active.
 */
export const PlattCharacter = React.forwardRef<CharacterHandle, PlattCharacterProps>(function PlattCharacter(
  props,
  ref,
) {
  return (
    <CharacterErrorBoundary fallback={<ProceduralPlatt ref={ref} {...props} />}>
      <React.Suspense fallback={<ProceduralPlatt ref={ref} {...props} />}>
        <PlattCharacterGLB ref={ref} {...props} />
      </React.Suspense>
    </CharacterErrorBoundary>
  );
});
