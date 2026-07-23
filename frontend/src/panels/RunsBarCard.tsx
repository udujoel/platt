import React from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DayPoint } from "./dashboard-metrics";

const tooltipStyle: React.CSSProperties = {
  background: "#161b24",
  border: "1px solid rgba(244,247,251,0.15)",
  borderRadius: 8,
  fontSize: 12,
};

export function RunsBarCard({ points }: { points: DayPoint[] }) {
  return (
    <section className="dashCard" aria-labelledby="runs-heading">
      <header className="dashCardHeader">
        <h2 id="runs-heading">Runs by day</h2>
        <span className="dashCardSubtitle">audit-recorded tool runs</span>
      </header>
      <div className="chartBox">
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={points} margin={{ top: 8, right: 12, left: -18, bottom: 0 }} barCategoryGap="28%">
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
            <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#f4f7fb" }} cursor={{ fill: "rgba(244,247,251,0.05)" }} formatter={(value) => [value, "runs"]} />
            <Bar dataKey="count" fill="#2dd4bf" radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
