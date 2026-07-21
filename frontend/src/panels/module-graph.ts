import type { Edge, Node } from "reactflow";

export type ModuleGraphNode = {
  path: string;
  variables: string[];
  outputs: string[];
  dependsOn: string[];
};

/**
 * Seeded module graph standing in for the real Terraform module dependency
 * graph parsed from HCL at onboarding time (F2).
 */
export const seededModuleGraphNodes: ModuleGraphNode[] = [
  { path: ".", variables: ["environment", "location"], outputs: [], dependsOn: ["modules/networking", "modules/storage-account"] },
  { path: "modules/networking", variables: ["address_space", "subnet_count"], outputs: ["vnet_id", "subnet_ids"], dependsOn: [] },
  { path: "modules/storage-account", variables: ["account_tier", "replication_type"], outputs: ["storage_account_id"], dependsOn: ["modules/networking"] },
];

export function describeModuleNode(node: ModuleGraphNode): string {
  const path = node.path === "." ? "root module" : node.path;
  const variables = node.variables.length > 0 ? node.variables.join(", ") : "none";
  return `${path} — variables: ${variables}`;
}

/**
 * Lays modules out in dependency-depth columns (roots on the left) since the
 * seeded graph is small and acyclic; a real collector would carry a layout
 * hint or run this through an actual DAG layered layout.
 */
export function buildModuleGraphElements(nodes: ModuleGraphNode[]): { nodes: Node[]; edges: Edge[] } {
  const depthByPath = new Map<string, number>();
  const nodeByPath = new Map(nodes.map((node) => [node.path, node]));

  function depthOf(path: string, seen: Set<string> = new Set()): number {
    if (depthByPath.has(path)) return depthByPath.get(path)!;
    if (seen.has(path)) return 0; // guards against an accidental cycle in seeded/collected data
    seen.add(path);
    const node = nodeByPath.get(path);
    const depth = !node || node.dependsOn.length === 0 ? 0 : 1 + Math.max(...node.dependsOn.map((dep) => depthOf(dep, seen)));
    depthByPath.set(path, depth);
    return depth;
  }

  const countAtDepth = new Map<number, number>();
  const flowNodes: Node[] = nodes.map((node) => {
    const depth = depthOf(node.path);
    const row = countAtDepth.get(depth) ?? 0;
    countAtDepth.set(depth, row + 1);
    return {
      id: node.path,
      position: { x: depth * 220, y: row * 110 },
      data: { label: node.path === "." ? "root" : node.path, node },
      type: "default",
    };
  });

  const flowEdges: Edge[] = nodes.flatMap((node) =>
    node.dependsOn.map((dep) => ({ id: `${dep}->${node.path}`, source: dep, target: node.path })),
  );

  return { nodes: flowNodes, edges: flowEdges };
}
