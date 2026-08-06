import React from "react";
import ReactFlow, { Background, Controls } from "reactflow";
import type { Node } from "reactflow";
import "reactflow/dist/style.css";
import { Network } from "lucide-react";
import { buildModuleGraphElements, describeModuleNode } from "./module-graph";
import type { ModuleGraphNode } from "./module-graph";
import { useDashboardStore } from "./dashboard-store";

export function ModuleGraphCard({ tall = false }: { tall?: boolean }) {
  const [selectedNode, setSelectedNode] = React.useState<ModuleGraphNode | null>(null);
  const moduleGraph = useDashboardStore((store) => store.moduleGraph);

  const { nodes: graphNodes, edges: graphEdges } = React.useMemo(
    () => buildModuleGraphElements(moduleGraph.value),
    [moduleGraph.value],
  );

  const onNodeClick = React.useCallback((_event: React.MouseEvent, node: Node) => {
    setSelectedNode((node.data as { node: ModuleGraphNode }).node);
  }, []);

  return (
    <section className="dashCard moduleGraphCard" aria-labelledby="module-graph-heading">
      <header className="dashCardHeader">
        <h2 id="module-graph-heading"><Network size={14} aria-hidden="true" /> Module graph</h2>
        {moduleGraph.source === "unavailable" ? (
          <span className="seededPill" title="Not connected to Azure DevOps yet" aria-label="Seeded sample data — not connected to Azure DevOps yet">
            seeded
          </span>
        ) : null}
      </header>
      <div className={`moduleGraphCanvas ${tall ? "tall" : ""}`}>
        <ReactFlow nodes={graphNodes} edges={graphEdges} onNodeClick={onNodeClick} fitView proOptions={{ hideAttribution: true }}>
          <Background gap={16} color="rgba(244,247,251,0.08)" />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <p className="moduleGraphDetail">
        {selectedNode ? describeModuleNode(selectedNode) : "Click a node to see its file path and variables."}
      </p>
    </section>
  );
}
