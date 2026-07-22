import React from "react";
import { useFrame } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import type { Group } from "three";
import { usePlattSceneStore } from "./scene-store";
import { BUBBLE_HIDE_DELAY_MS, isBubbleVisible, truncateBubbleText } from "./speech-bubble";
import { getThreeStagePose } from "../three-stage-pose";

/** Approximate head height above the rig's base anchor (rig has no exposed bone to parent to directly). */
const HEAD_OFFSET_Y = 1.55;

/**
 * Speech bubble: a drei Html element tracking the character's approximate head position each
 * frame (per PRD 5.3), streaming the current assistant text (truncated per scene/speech-bubble.ts),
 * hiding BUBBLE_HIDE_DELAY_MS after the message completes. Full text always lives in the chat panel.
 */
export function Bubble({ portalTarget }: { portalTarget?: React.RefObject<HTMLElement | null> } = {}) {
  const state = usePlattSceneStore((s) => s.state);
  const speech = usePlattSceneStore((s) => s.speech);
  const headAnchor = usePlattSceneStore((s) => s.headAnchor);
  const groupRef = React.useRef<Group>(null);
  const wasTalking = React.useRef(false);
  const [completedAt, setCompletedAt] = React.useState<number | null>(null);
  const [now, setNow] = React.useState<number | null>(null);

  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    // Prefer the rig's live world anchor (set by PlattController, e.g. during idle wander) so the
    // bubble tracks Platt even off the canned pose; fall back to the pose approximation until that
    // is published for the current state.
    if (headAnchor) {
      const [ax, ay, az] = headAnchor;
      groupRef.current.position.set(ax, ay + HEAD_OFFSET_Y, az + 0.2);
      return;
    }
    const pose = getThreeStagePose(state, clock.getElapsedTime());
    groupRef.current.position.set(pose.x, pose.y + HEAD_OFFSET_Y, 0.2);
  });

  React.useEffect(() => {
    if (state === "talking") {
      wasTalking.current = true;
    } else if (wasTalking.current) {
      wasTalking.current = false;
      setCompletedAt(Date.now());
    }
  }, [state]);

  React.useEffect(() => {
    if (completedAt === null) return;
    setNow(Date.now());
    const id = window.setTimeout(() => setNow(Date.now()), BUBBLE_HIDE_DELAY_MS);
    return () => window.clearTimeout(id);
  }, [completedAt]);

  const visible = isBubbleVisible({
    state,
    hasSpeech: speech.length > 0,
    msSinceMessageComplete: completedAt === null || now === null ? null : now - completedAt,
  });

  return (
    <group ref={groupRef}>
      {visible ? (
        <Html
          center
          distanceFactor={7}
          occlude={false}
          zIndexRange={[20, 0]}
          portal={portalTarget as React.RefObject<HTMLElement> | undefined}
        >
          <div className="threeSpeechBubble" role="status" aria-live="polite" aria-atomic="true">
            {truncateBubbleText(speech)}
          </div>
        </Html>
      ) : null}
    </group>
  );
}
