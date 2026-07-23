import React from "react";
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { GitPullRequest } from "lucide-react";
import { averagePassRate, formatAge, isVersionCurrent, seededDashboardData } from "./dashboard-data";

export function PipelinesView() {
  const { pipelines, openPullRequests, versions, seeded } = seededDashboardData;

  return (
    <div className="pipelinesViewGrid">
      {seeded ? <p className="seededBadge">Seeded data — real collectors land in a later wave</p> : null}
      <section className="dashCard" aria-labelledby="pipelines-heading">
        <header className="dashCardHeader">
          <h2 id="pipelines-heading">Pipeline pass rate</h2>
        </header>
        {pipelines.map((series) => (
          <div className="sparklineRow" key={series.name}>
            <div className="sparklineLabel">
              <strong>{series.name}</strong>
              <span>{averagePassRate(series)}% avg</span>
            </div>
            <div className="sparklineChart">
              <ResponsiveContainer width="100%" height={44}>
                <LineChart data={series.points}>
                  <YAxis hide domain={[0, 100]} />
                  <Tooltip
                    formatter={(value) => [`${value}%`, "pass rate"]}
                    contentStyle={{ background: "#161b24", border: "1px solid rgba(244,247,251,0.15)", fontSize: 12, borderRadius: 8 }}
                  />
                  <Line type="monotone" dataKey="passRate" stroke="#2dd4bf" strokeWidth={2} dot={false} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </section>

      <section className="dashCard" aria-labelledby="prs-heading">
        <header className="dashCardHeader">
          <h2 id="prs-heading">Open pull requests</h2>
        </header>
        <ol className="openPrList">
          {openPullRequests.map((pr) => (
            <li key={pr.id}>
              <GitPullRequest size={14} aria-hidden="true" />
              {pr.url ? (
                <a href={pr.url} target="_blank" rel="noreferrer">{pr.title}</a>
              ) : (
                <span className="prTitleSample" title="Seeded sample data — not a real pull request">{pr.title}</span>
              )}
              <span>{formatAge(pr.ageDays)}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="dashCard" aria-labelledby="versions-heading">
        <header className="dashCardHeader">
          <h2 id="versions-heading">Version posture</h2>
        </header>
        <ul className="versionList">
          {versions.map((version) => (
            <li key={version.name} className={isVersionCurrent(version) ? "current" : "behind"}>
              <span>{version.name}</span>
              <span>{version.current}{isVersionCurrent(version) ? "" : ` → ${version.latest}`}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
