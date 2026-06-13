import type { Edge, Node } from "@xyflow/react";

import type { GraphResponse } from "./types";

// Spacing between layout columns/rows, in React Flow coordinate units.
const COL_WIDTH = 260;
const ROW_HEIGHT = 90;
// Number of columns used by the cycle/fallback grid layout.
const FALLBACK_COLS = 4;

/**
 * Convert a backend GraphResponse into React Flow nodes and edges.
 *
 * Layout is a simple left-to-right layered DAG: a node's column is its longest
 * path from a root (relaxed along edges in the backend's topological order),
 * and nodes sharing a column are stacked vertically. When a cycle is present
 * (no execution order), we fall back to a deterministic grid so the nodes and
 * edges still render and the cycle is visible.
 *
 * Pure and dependency-free so it can be unit-tested without mounting React Flow.
 */
export function buildFlowElements(graph: GraphResponse): {
  nodes: Node[];
  edges: Edge[];
} {
  const edges: Edge[] = graph.edges.map((e) => ({
    id: `${e.config_key}:${e.source}->${e.target}`,
    source: e.source,
    target: e.target,
    label: e.config_key,
  }));

  const depth = computeDepths(graph);

  // Track how many nodes we have already placed in each column.
  const rowCursor = new Map<number, number>();
  const nodes: Node[] = graph.nodes.map((name) => {
    const col = depth.get(name) ?? 0;
    const row = rowCursor.get(col) ?? 0;
    rowCursor.set(col, row + 1);
    return {
      id: name,
      position: { x: col * COL_WIDTH, y: row * ROW_HEIGHT },
      data: { label: name },
    };
  });

  return { nodes, edges };
}

function computeDepths(graph: GraphResponse): Map<string, number> {
  const depth = new Map<string, number>();
  for (const name of graph.nodes) depth.set(name, 0);

  const order = graph.execution_order;
  if (!order || graph.cycle_detected) {
    // No topological order available — lay out in a stable grid.
    graph.nodes.forEach((name, i) => depth.set(name, i % FALLBACK_COLS));
    return depth;
  }

  const outgoing = new Map<string, string[]>();
  for (const e of graph.edges) {
    const targets = outgoing.get(e.source) ?? [];
    targets.push(e.target);
    outgoing.set(e.source, targets);
  }

  // Relax depths in topological order: a target sits one column right of the
  // deepest source that reaches it.
  for (const name of order) {
    const base = depth.get(name) ?? 0;
    for (const target of outgoing.get(name) ?? []) {
      depth.set(target, Math.max(depth.get(target) ?? 0, base + 1));
    }
  }

  return depth;
}
