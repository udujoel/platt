import React from "react";
import type { PlattState } from "../backend-events";
import { usePlattSceneStore } from "../scene/scene-store";
import { amplitudeAtElapsed, type BoundaryPulse } from "./speech-amplitude-envelope";
import { isSpeechSynthesisSupported } from "./speech-support";
import { shouldCancelSpeaking, shouldStartSpeaking } from "./tts-decision";

/**
 * Speaks Platt's assistant messages via `speechSynthesis` while he's `talking` (PRD F8), and
 * drives the character's jaw amplitude off word-boundary pulses for the duration of the
 * utterance. All start/cancel decisions come from the pure `tts-decision` module; this hook only
 * owns the imperative `speechSynthesis` calls and the per-frame amplitude sampling loop.
 */
export function useSpeechSynthesis({
  state,
  muted,
  text,
  messageId,
}: {
  state: PlattState;
  muted: boolean;
  text: string;
  messageId: string | null;
}) {
  const supported = React.useMemo(() => isSpeechSynthesisSupported(typeof window === "undefined" ? undefined : window), []);
  const setJawAmplitude = usePlattSceneStore((s) => s.setJawAmplitude);

  const lastSpokenId = React.useRef<string | null>(null);
  const isSpeakingRef = React.useRef(false);
  const frameRef = React.useRef<number | null>(null);

  const stopJawLoop = React.useCallback(() => {
    if (frameRef.current !== null) {
      cancelAnimationFrame(frameRef.current);
      frameRef.current = null;
    }
    setJawAmplitude(0);
  }, [setJawAmplitude]);

  React.useEffect(() => {
    if (!supported) return undefined;

    if (shouldCancelSpeaking({ state, muted, isSpeaking: isSpeakingRef.current })) {
      window.speechSynthesis.cancel();
      isSpeakingRef.current = false;
      stopJawLoop();
    }

    if (messageId && shouldStartSpeaking({ state, muted, text, messageId, lastSpokenMessageId: lastSpokenId.current })) {
      lastSpokenId.current = messageId;
      window.speechSynthesis.cancel();

      const pulses: BoundaryPulse[] = [];
      const startedAt = performance.now();
      const utterance = new SpeechSynthesisUtterance(text);

      utterance.onboundary = () => {
        pulses.push({ elapsedMs: performance.now() - startedAt });
      };
      utterance.onstart = () => {
        isSpeakingRef.current = true;
        const tick = () => {
          setJawAmplitude(amplitudeAtElapsed(pulses, performance.now() - startedAt));
          frameRef.current = requestAnimationFrame(tick);
        };
        frameRef.current = requestAnimationFrame(tick);
      };
      const finish = () => {
        isSpeakingRef.current = false;
        stopJawLoop();
      };
      utterance.onend = finish;
      utterance.onerror = finish;

      window.speechSynthesis.speak(utterance);
    }

    return undefined;
  }, [messageId, muted, setJawAmplitude, state, stopJawLoop, supported, text]);

  React.useEffect(() => {
    if (!supported) return undefined;
    return () => {
      window.speechSynthesis.cancel();
      stopJawLoop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [supported]);

  return { supported };
}
