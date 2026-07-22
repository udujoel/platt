import React from "react";
import { Volume2, VolumeX } from "lucide-react";
import { isSpeechSynthesisSupported } from "./speech-support";
import { useVoiceMuteStore } from "./mute-store";

/**
 * Mute toggle for Platt's spoken replies (PRD §6). Hidden when `speechSynthesis` is unavailable,
 * since there's nothing to mute — graceful degradation matches `MicButton`.
 */
export function MuteToggle() {
  const muted = useVoiceMuteStore((s) => s.muted);
  const toggleMute = useVoiceMuteStore((s) => s.toggleMute);
  const supported = React.useMemo(() => isSpeechSynthesisSupported(typeof window === "undefined" ? undefined : window), []);

  if (!supported) return null;

  return (
    <button
      type="button"
      className={`muteToggle ${muted ? "muted" : ""}`}
      aria-label={muted ? "Unmute Platt's voice" : "Mute Platt's voice"}
      aria-pressed={muted}
      title={muted ? "Unmute Platt's voice" : "Mute Platt's voice"}
      onClick={toggleMute}
    >
      {muted ? <VolumeX size={16} aria-hidden="true" /> : <Volume2 size={16} aria-hidden="true" />}
    </button>
  );
}
