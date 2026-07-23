import React from "react";
import { clampPercent } from "./dashboard-metrics";

const RADIUS = 70;
const STROKE = 12;
const CENTER = 84;
const CIRCUMFERENCE_HALF = Math.PI * RADIUS;

function toneColor(value: number): string {
  if (value >= 80) return "#2dd4bf";
  if (value >= 55) return "#ffb454";
  return "#f87171";
}

/** Semicircular radial gauge — thin arc, rounded data-end, single-hue fill against a recessive track. */
export function GaugeCard({ label, value, caption }: { label: string; value: number; caption?: string }) {
  const percent = clampPercent(value);
  const offset = CIRCUMFERENCE_HALF * (1 - percent / 100);
  const color = toneColor(percent);

  return (
    <section className="dashCard gaugeCard" aria-labelledby="gauge-heading">
      <header className="dashCardHeader">
        <h2 id="gauge-heading">{label}</h2>
      </header>
      <div className="gaugeVisual" role="img" aria-label={`${label}: ${percent}%`}>
        <svg viewBox="0 0 168 96" width="100%">
          <path
            d={`M ${CENTER - RADIUS} ${CENTER} A ${RADIUS} ${RADIUS} 0 0 1 ${CENTER + RADIUS} ${CENTER}`}
            fill="none"
            stroke="rgba(244,247,251,0.14)"
            strokeWidth={STROKE}
            strokeLinecap="round"
          />
          <path
            d={`M ${CENTER - RADIUS} ${CENTER} A ${RADIUS} ${RADIUS} 0 0 1 ${CENTER + RADIUS} ${CENTER}`}
            fill="none"
            stroke={color}
            strokeWidth={STROKE}
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE_HALF}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 420ms ease, stroke 420ms ease" }}
          />
        </svg>
        <div className="gaugeReadout">
          <strong style={{ color }}>{percent}%</strong>
          {caption ? <span>{caption}</span> : null}
        </div>
      </div>
    </section>
  );
}
