import React from "react";
import type { LucideIcon } from "lucide-react";

export type KpiTone = "neutral" | "good" | "warning" | "critical";

export function KpiTile({
  label,
  value,
  icon: Icon,
  tone = "neutral",
  detail,
  seeded,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: KpiTone;
  detail?: string;
  seeded?: boolean;
}) {
  return (
    <div className={`kpiTile tone-${tone}`}>
      <div className="kpiTileTop">
        <span className="kpiTileIcon" aria-hidden="true">
          <Icon size={16} />
        </span>
        <span className="kpiTileLabel">{label}</span>
      </div>
      <p className="kpiTileValue">{value}</p>
      <div className="kpiTileFoot">
        {detail ? <span className="kpiTileDetail">{detail}</span> : null}
        {seeded ? (
          <span className="kpiTileSeeded" title="Not connected to Azure DevOps yet" aria-label="Seeded sample data — not connected to Azure DevOps yet">
            seeded
          </span>
        ) : null}
      </div>
    </div>
  );
}
