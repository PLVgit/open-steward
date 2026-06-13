import { describe, expect, it } from "vitest";

import { buildFlowElements } from "./graphLayout";
import type { GraphResponse } from "./types";

function graph(partial: Partial<GraphResponse>): GraphResponse {
  return {
    nodes: [],
    edges: [],
    execution_order: [],
    cycle_detected: false,
    ...partial,
  };
}

describe("buildFlowElements", () => {
  it("returns a node per table and an edge per dependency", () => {
    const { nodes, edges } = buildFlowElements(
      graph({
        nodes: ["a", "b", "c"],
        edges: [
          { source: "a", target: "b", config_key: "etl_1" },
          { source: "b", target: "c", config_key: "etl_2" },
        ],
        execution_order: ["a", "b", "c"],
      }),
    );
    expect(nodes.map((n) => n.id).sort()).toEqual(["a", "b", "c"]);
    expect(edges).toHaveLength(2);
  });

  it("lays out a linear chain in increasing columns (x)", () => {
    const { nodes } = buildFlowElements(
      graph({
        nodes: ["a", "b", "c"],
        edges: [
          { source: "a", target: "b", config_key: "etl_1" },
          { source: "b", target: "c", config_key: "etl_2" },
        ],
        execution_order: ["a", "b", "c"],
      }),
    );
    const x = (id: string) => nodes.find((n) => n.id === id)!.position.x;
    expect(x("a")).toBeLessThan(x("b"));
    expect(x("b")).toBeLessThan(x("c"));
  });

  it("labels each edge with its config_key", () => {
    const { edges } = buildFlowElements(
      graph({
        nodes: ["a", "b"],
        edges: [{ source: "a", target: "b", config_key: "etl_42" }],
        execution_order: ["a", "b"],
      }),
    );
    expect(edges[0].label).toBe("etl_42");
    expect(edges[0].source).toBe("a");
    expect(edges[0].target).toBe("b");
  });

  it("still returns all nodes and edges when a cycle is present", () => {
    const { nodes, edges } = buildFlowElements(
      graph({
        nodes: ["a", "b"],
        edges: [
          { source: "a", target: "b", config_key: "etl_1" },
          { source: "b", target: "a", config_key: "etl_2" },
        ],
        execution_order: null,
        cycle_detected: true,
      }),
    );
    expect(nodes).toHaveLength(2);
    expect(edges).toHaveLength(2);
  });

  it("handles an empty graph", () => {
    const { nodes, edges } = buildFlowElements(graph({ nodes: [], edges: [] }));
    expect(nodes).toEqual([]);
    expect(edges).toEqual([]);
  });
});
