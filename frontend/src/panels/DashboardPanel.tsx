import React from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import type { Node } from "reactflow";
import "reactflow/dist/style.css";
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from "recharts";
import { GitPullRequest, LayoutDashboard } from "lucide-react";
import { averagePassRate, formatAge, isVersionCurrent, seededDashboardData } from "./dashboard-data";
import { buildModuleGraphElements, describeModuleNode, seededModuleGraphNodes } from "./module-graph";
import type { ModuleGraphNode } from "./module-graph";

const { nodes: graphNodes, edges: graphEdges } = buildModuleGraphElements(seededModuleGraphNodes);

export function DashboardPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [selectedNode, setSelectedNode] = React.useState<ModuleGraphNode | null>(null);
  const { pipelines, openPullRequests, versions, seeded } = seededDashboardData;

  const onNodeClick = React.useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode((node.data as { node: ModuleGraphNode }).node);
  }, []);

  return (
    <section className={`slideOverPanel dashboardPanel ${open ? "open" : ""}`} aria-hidden={!open} aria-label="Platform health dashboard">
      <header className="slideOverHeader">
        <div>
          <p className="eyebrow">Platform health</p>
          <h1>Dashboard</h1>
        </div>
        <button className="iconButton" type="button" onClick={onClose} aria-label="Close dashboard panel">
          &times;
        </button>
      </header>

      {seeded ? <p className="seededBadge">Seeded data — real collectors land in a later wave</p> : null}

      <div className="dashboardBody">
        <section className="dashboardCard" aria-labelledby="dashboard-pipelines-heading">
          <h2 id="dashboard-pipelines-heading">Pipeline pass rate</h2>
          {pipelines.map((series) => (
            <div className="sparklineRow" key={series.name}>
              <div className="sparklineLabel">
                <strong>{series.name}</strong>
                <span>{averagePassRate(series)}% avg</span>
              </div>
              <div className="sparklineChart">
                <ResponsiveContainer width="100%" height={40}>
                  <LineChart data={series.points}>
                    <YAxis hide domain={[0, 100]} />
                    <Tooltip
                      formatter={(value) => [`${value}%`, "pass rate"]}
                      contentStyle={{ background: "#161b24", border: "1px solid rgba(244,247,251,0.15)", fontSize: 12 }}
                    />
                    <Line type="monotone" dataKey="passRate" stroke="#2dd4bf" strokeWidth={2} dot={false} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          ))}
        </section>

        <section className="dashboardCard" aria-labelledby="dashboard-prs-heading">
          <h2 id="dashboard-prs-heading">Open pull requests</h2>
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

        <section className="dashboardCard" aria-labelledby="dashboard-versions-heading">
          <h2 id="dashboard-versions-heading">Version posture</h2>
          <ul className="versionList">
            {versions.map((version) => (
              <li key={version.name} className={isVersionCurrent(version) ? "current" : "behind"}>
                <span>{version.name}</span>
                <span>{version.current}{isVersionCurrent(version) ? "" : ` → ${version.latest}`}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="dashboardCard moduleGraphCard" aria-labelledby="dashboard-graph-heading">
          <h2 id="dashboard-graph-heading"><LayoutDashboard size={14} aria-hidden="true" /> Module graph</h2>
          <div className="moduleGraphCanvas">
            <ReactFlow nodes={graphNodes} edges={graphEdges} onNodeClick={onNodeClick} fitView proOptions={{ hideAttribution: true }}>
              <Background gap={16} />
              <Controls showInteractive={false} />
            </ReactFlow>
          </div>
          <p className="moduleGraphDetail">
            {selectedNode ? describeModuleNode(selectedNode) : "Click a node to see its file path and variables."}
          </p>
        </section>
      </div>
    </section>
  );
}
