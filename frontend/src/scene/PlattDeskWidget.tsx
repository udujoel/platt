import React from "react";
import { selectStageRenderer } from "../stage-renderer";
import type { StageRenderer } from "../stage-renderer";
import type { ThreeStageState } from "../three-stage-pose";
import { deskFallbackMonitorColor, deskFallbackStatusLabel } from "./desk-widget-2d";

const DeskScene3D = React.lazy(() => import("./DeskScene3D"));

const DESK_WIDGET_SIZE_PX = 320;

function browserSupportsWebGL(): boolean {
  try {
    return Boolean(document.createElement("canvas").getContext("webgl"));
  } catch {
    return false;
  }
}

class DeskSceneBoundary extends React.Component<
  { children: React.ReactNode; fallback: React.ReactNode; onFailure: () => void },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch() {
    this.props.onFailure();
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

/** Mirrors `main.tsx`'s stage-renderer selection (reduced-motion / WebGL support), scoped to this widget. */
function useDeskStageRenderer(): [StageRenderer, () => void] {
  const [renderer, setRenderer] = React.useState<StageRenderer>("fallback");
  const useFallback = React.useCallback(() => setRenderer("fallback"), []);

  React.useEffect(() => {
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const refreshRenderer = () => {
      setRenderer(
        selectStageRenderer({
          prefersReducedMotion: motionQuery.matches,
          supportsWebGL: browserSupportsWebGL(),
        }),
      );
    };

    refreshRenderer();
    motionQuery.addEventListener("change", refreshRenderer);
    return () => motionQuery.removeEventListener("change", refreshRenderer);
  }, []);

  return [renderer, useFallback];
}

/** CSS-only cozy desk nook, used when reduced-motion is on, WebGL is unavailable, or the 3D chunk fails to load. */
function PlattDeskWidget2D({ state, speech }: { state: ThreeStageState; speech: string }) {
  const monitorColor = deskFallbackMonitorColor(state);
  const statusLabel = deskFallbackStatusLabel(state);

  return (
    <div className="pdw-2d" role="img" aria-label={`Platt is ${statusLabel} at their desk`}>
      <div className="pdw-2d-wall">
        <div className="pdw-2d-window" />
      </div>
      <div className="pdw-2d-lamp" style={{ boxShadow: "0 0 12px 4px rgba(255, 180, 84, 0.55)" }} />
      <div className="pdw-2d-desk">
        <div className="pdw-2d-monitor" style={{ background: monitorColor, boxShadow: `0 0 8px 1px ${monitorColor}` }} />
      </div>
      <div className={`pdw-2d-platt ${state}`}>
        <div className="pdw-2d-head" />
        <div className="pdw-2d-body" />
      </div>
      <div className="pdw-2d-chair" />
      {speech ? <span className="pdw-2d-sr-only">{speech}</span> : null}
    </div>
  );
}

const DESK_WIDGET_STYLE = `
.pdw-root {
  position: relative;
  width: ${DESK_WIDGET_SIZE_PX}px;
  max-width: 100%;
  aspect-ratio: 1;
  border-radius: 12px;
  overflow: hidden;
  background: #161c26;
}
.pdw-root canvas {
  display: block;
  width: 100% !important;
  height: 100% !important;
}
.pdw-2d {
  position: relative;
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, #1b2330 0%, #161c26 62%, #11151d 100%);
  overflow: hidden;
}
.pdw-2d-wall {
  position: absolute;
  inset: 0 0 55% 0;
  background: #1b2330;
}
.pdw-2d-window {
  position: absolute;
  top: 14%;
  right: 12%;
  width: 26%;
  height: 34%;
  background: #3a3120;
  box-shadow: 0 0 18px 6px rgba(255, 180, 84, 0.3);
  border-radius: 4px;
}
.pdw-2d-lamp {
  position: absolute;
  top: 34%;
  right: 22%;
  width: 10%;
  height: 10%;
  border-radius: 50%;
  background: #ffb454;
}
.pdw-2d-desk {
  position: absolute;
  left: 14%;
  right: 10%;
  bottom: 18%;
  height: 12%;
  background: #9d6037;
  border-radius: 3px;
}
.pdw-2d-monitor {
  position: absolute;
  top: -46%;
  left: 32%;
  width: 34%;
  height: 60%;
  border-radius: 3px;
}
.pdw-2d-chair {
  position: absolute;
  left: 40%;
  bottom: 4%;
  width: 26%;
  height: 16%;
  background: #2f3742;
  border-radius: 3px 3px 0 0;
}
.pdw-2d-platt {
  position: absolute;
  left: 44%;
  bottom: 16%;
  width: 18%;
  height: 30%;
  transition: transform 0.4s ease;
}
.pdw-2d-platt.concerned {
  transform: translateY(2%) rotate(-2deg);
}
.pdw-2d-platt.celebrating {
  transform: translateY(-6%);
}
.pdw-2d-head {
  width: 55%;
  height: 42%;
  margin: 0 auto;
  border-radius: 50%;
  background: #d99a70;
}
.pdw-2d-body {
  width: 100%;
  height: 58%;
  border-radius: 6px 6px 3px 3px;
  background: #304969;
}
.pdw-2d-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
}
`;

/**
 * Default export: the compact bottom-right corner desk widget (per the desk-widget task). A
 * fixed ~320px square, lazy-loads the R3F canvas (kept as a separate chunk) behind an error
 * boundary + Suspense that both fall back to a CSS-only 2D nook, matching `main.tsx`'s existing
 * stage-renderer selection (reduced motion / no WebGL / a lost context all degrade the same way).
 * The dashboard mounts this wherever it wants Platt to sit; it owns no page-level positioning.
 */
export function PlattDeskWidget({
  state,
  speech = "",
  className,
}: {
  state: ThreeStageState;
  speech?: string;
  className?: string;
}) {
  const [renderer, useFallback] = useDeskStageRenderer();

  return (
    <div className={className ? `pdw-root ${className}` : "pdw-root"} aria-label="Platt's desk">
      <style>{DESK_WIDGET_STYLE}</style>
      {renderer === "three" ? (
        <DeskSceneBoundary fallback={<PlattDeskWidget2D state={state} speech={speech} />} onFailure={useFallback}>
          <React.Suspense fallback={<PlattDeskWidget2D state={state} speech={speech} />}>
            <DeskScene3D state={state} speech={speech} onContextLost={useFallback} />
          </React.Suspense>
        </DeskSceneBoundary>
      ) : (
        <PlattDeskWidget2D state={state} speech={speech} />
      )}
    </div>
  );
}

export default PlattDeskWidget;
