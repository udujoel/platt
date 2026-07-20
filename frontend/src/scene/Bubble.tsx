import React from "react";
import { usePlattSceneStore } from "./scene-store";
import { isBubbleVisible, truncateBubbleText } from "./speech-bubble";

/**
 * Speech bubble: streams the current assistant text (truncated per scene/bubble.ts), hides
 * BUBBLE_HIDE_DELAY_MS after the message completes. Full text always lives in the chat panel.
 */
export function Bubble() {
  const state = usePlattSceneStore((s) => s.state);
  const speech = usePlattSceneStore((s) => s.speech);
  const wasTalking = React.useRef(false);
  const [completedAt, setCompletedAt] = React.useState<number | null>(null);
  const [now, setNow] = React.useState<number | null>(null);

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
    const id = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(id);
  }, [completedAt]);

  const visible = isBubbleVisible({
    state,
    hasSpeech: speech.length > 0,
    msSinceMessageComplete: completedAt === null || now === null ? null : now - completedAt,
  });

  if (!visible) return null;

  return (
    <div className="threeSpeechBubble" role="status" aria-live="polite" aria-atomic="true">
      {truncateBubbleText(speech)}
    </div>
  );
}
