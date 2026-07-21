import React from "react";
import { CharacterErrorBoundary } from "./CharacterErrorBoundary";
import { createCharacterHandleRelay } from "./character-handle-relay";
import { PlattCharacterGLB } from "./PlattCharacterGLB";
import { ProceduralPlatt } from "./ProceduralPlatt";
import type { CharacterHandle, PlattCharacterProps } from "./types";

/**
 * Selects the glb-driven `platt.glb` character (T-D1, `PlattCharacterGLB`) when it loads
 * successfully, falling back to the procedural rig (`ProceduralPlatt`) while it loads and if
 * the asset is missing or fails to parse — see `ASSETS.md` for how to produce `platt.glb`.
 * `PlattController` only ever renders this component and only ever needs the `CharacterHandle`
 * contract, so it doesn't need to know (or change) which rig is actually active.
 *
 * The ref exposed to the caller is a `character-handle-relay`, not either child directly: a
 * Suspense/error-boundary swap mounts a brand-new child instance that has no memory of the
 * crossfade that was already running, so the relay replays the last `CrossfadePlan` onto
 * whichever child attaches next.
 */
export const PlattCharacter = React.forwardRef<CharacterHandle, PlattCharacterProps>(function PlattCharacter(
  props,
  ref,
) {
  const relay = React.useRef(createCharacterHandleRelay(props.clip)).current;

  React.useImperativeHandle(ref, () => relay.handle, [relay]);

  return (
    <CharacterErrorBoundary fallback={<ProceduralPlatt ref={relay.attach} {...props} />}>
      <React.Suspense fallback={<ProceduralPlatt ref={relay.attach} {...props} />}>
        <PlattCharacterGLB ref={relay.attach} {...props} />
      </React.Suspense>
    </CharacterErrorBoundary>
  );
});
