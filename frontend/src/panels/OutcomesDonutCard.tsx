import React from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import type { OutcomeSlice } from "./dashboard-metrics";

const statusColor: Record<string, string> = {
  Success: "#2dd4bf",
  Warning: "#ffb454",
  Failure: "#f87171",
};

const tooltipStyle: React.CSSProperties = {
  background: "#161b24",
  border: "1px solid rgba(244,247,251,0.15)",
  borderRadius: 8,
  fontSize: 12,
};

export function OutcomesDonutCard({ slices }: { slices: OutcomeSlice[] }) {
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);

  return (
    <section className="dashCard" aria-labelledby="outcomes-heading">
      <header className="dashCardHeader">
        <h2 id="outcomes-heading">Job outcomes</h2>
        <span className="dashCardSubtitle">{total} audited runs</span>
      </header>
      {total === 0 ? (
        <p className="dashCardEmpty">No audit outcomes recorded yet.</p>
      ) : (
        <div className="donutRow">
          <div className="chartBox donutBox">
            <ResponsiveContainer width="100%" height={150}>
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={44}
                  outerRadius={66}
                  paddingAngle={slices.length > 1 ? 3 : 0}
                  strokeWidth={2}
                  stroke="#21252f"
                  isAnimationActive={false}
                >
                  {slices.map((slice) => (
                    <Cell key={slice.name} fill={statusColor[slice.name] ?? "#8bb8ff"} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => [value, name]} />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="donutLegend">
            {slices.map((slice) => (
              <li key={slice.name}>
                <span className="donutLegendDot" style={{ background: statusColor[slice.name] ?? "#8bb8ff" }} aria-hidden="true" />
                <span>{slice.name}</span>
                <strong>{slice.value}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
