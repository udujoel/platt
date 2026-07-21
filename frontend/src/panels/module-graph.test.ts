import { describe, expect, it } from "vitest";

import { buildModuleGraphElements, describeModuleNode, seededModuleGraphNodes } from "./module-graph";
import type { ModuleGraphNode } from "./module-graph";

describe("describeModuleNode", () => {
  it("renders the root module's path as 'root module'", () => {
    expect(describeModuleNode({ path: ".", variables: ["environment"], outputs: [], dependsOn: [] })).toBe(
      "root module — variables: environment",
    );
  });

  it("lists a nested module's file path and variables", () => {
    expect(
      describeModuleNode({ path: "modules/networking", variables: ["address_space", "subnet_count"], outputs: [], dependsOn: [] }),
    ).toBe("modules/networking — variables: address_space, subnet_count");
  });

  it("falls back to 'none' when a module declares no variables", () => {
    expect(describeModuleNode({ path: "modules/empty", variables: [], outputs: [], dependsOn: [] })).toBe(
      "modules/empty — variables: none",
    );
  });
});

describe("buildModuleGraphElements", () => {
  it("produces one React Flow node per module, each carrying its source node for detail rendering", () => {
    const { nodes } = buildModuleGraphElements(seededModuleGraphNodes);
    expect(nodes).toHaveLength(seededModuleGraphNodes.length);
    const networkingNode = nodes.find((node) => node.id === "modules/networking");
    expect(networkingNode?.data.label).toBe("modules/networking");
    expect(networkingNode?.data.node).toEqual(seededModuleGraphNodes[1]);
  });

  it("places dependency-free modules to the left of the modules that depend on them", () => {
    const { nodes } = buildModuleGraphElements(seededModuleGraphNodes);
    const networking = nodes.find((node) => node.id === "modules/networking")!;
    const storage = nodes.find((node) => node.id === "modules/storage-account")!;
    const root = nodes.find((node) => node.id === ".")!;
    expect(networking.position.x).toBeLessThan(storage.position.x);
    expect(storage.position.x).toBeLessThan(root.position.x);
  });

  it("emits one edge per dependency, pointing from dependency to dependent", () => {
    const { edges } = buildModuleGraphElements(seededModuleGraphNodes);
    expect(edges).toContainEqual({ id: "modules/networking->modules/storage-account", source: "modules/networking", target: "modules/storage-account" });
    expect(edges).toContainEqual({ id: "modules/networking->.", source: "modules/networking", target: "." });
    expect(edges).toContainEqual({ id: "modules/storage-account->.", source: "modules/storage-account", target: "." });
  });

  it("does not blow the stack on a self-referential dependency", () => {
    const cyclic: ModuleGraphNode[] = [{ path: "modules/weird", variables: [], outputs: [], dependsOn: ["modules/weird"] }];
    expect(() => buildModuleGraphElements(cyclic)).not.toThrow();
  });
});
