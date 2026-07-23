import React from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DayPoint } from "./dashboard-metrics";

const tooltipStyle: React.CSSProperties = {
  background: "#161b24",
  border: "1px solid rgba(244,247,251,0.15)",
  borderRadius: 8,
  fontSize: 12,
};

export function ActivityLineCard({ points }: { points: DayPoint[] }) {
  return (
    <section className="dashCard" aria-labelledby="activity-heading">
      <header className="dashCardHeader">
        <h2 id="activity-heading">Activity over time</h2>
        <span className="dashCardSubtitle">cumulative audit events, 7 days</span>
      </header>
      <div className="chartBox">
        <ResponsiveContainer width="100%" height={180}>
          <LineChart data={points} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
            <CartesianGrid stroke="rgba(244,247,251,0.06)" vertical={false} />
            <XAxis dataKey="label" tick={{ fill: "rgba(244,247,251,0.5)", fontSize: 11 }} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fill: "rgba(244,247,251,0.5)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              width={30}
              allowDecimals={false}
              domain={[0, (max: number) => Math.max(1, max)]}
            />
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#f4f7fb" }} formatter={(value) => [value, "events"]} />
            <Line type="monotone" dataKey="count" stroke="#2dd4bf" strokeWidth={2} dot={{ r: 3, fill: "#2dd4bf", strokeWidth: 0 }} activeDot={{ r: 5 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
