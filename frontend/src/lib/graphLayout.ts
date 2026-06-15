import { Position } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";

import type { GraphResponse } from "./types";

// Layout geometry, in React Flow coordinate units. Generous gaps give the
// dependency lines (especially the fan-out from high-degree source tables) room
// to breathe, so the default view reads cleanly without manual zoom.
const COL_WIDTH = 360;
const ROW_HEIGHT = 132;
// Wrap a column once it would exceed this many rows, so a lane with many tables
// becomes a balanced grid instead of one tall unreadable column.
const MAX_ROWS = 6;
// Columns used by the cycle/fallback depth heuristic.
const FALLBACK_COLS = 4;

export type TableKind = "source" | "staging" | "mart" | "unknown";

/** Classify a table into a visual category from its schema prefix. */
export function tableKind(table: string): TableKind {
  const schema = table.toLowerCase().split(".")[0] ?? "";
  if (/raw|source|landing|external|ingest/.test(schema)) return "source";
  if (/staging|stg/.test(schema)) return "staging";
  if (/mart|warehouse|dwh|gold|analytics/.test(schema)) return "mart";
  return "unknown";
}

// Lanes are laid out left → right in this order.
const LANE_ORDER: TableKind[] = ["source", "staging", "mart", "unknown"];

/**
 * Convert a backend GraphResponse into React Flow nodes and edges.
 *
 * Layout groups tables into namespace lanes (source → staging → mart → unknown),
 * left to right. Within a lane, nodes are ordered by dependency depth so chains
 * flow rightward, and each column wraps once it exceeds MAX_ROWS — preventing the
 * single tall column that makes wide configs unreadable. Shorter columns are
 * centered vertically against the tallest.
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
    // `label` is what React Flow renders; `data.configKey` is read by the
    // inspector. Labels are hidden by default and revealed on interaction
    // (see PipelineFlow) — keeping the default canvas clean for screenshots.
    label: e.config_key,
    data: { configKey: e.config_key },
  }));

  const depth = computeDepths(graph);
  const orderIndex = new Map(graph.nodes.map((name, i) => [name, i]));

  const byLane = new Map<TableKind, string[]>();
  for (const name of graph.nodes) {
    const kind = tableKind(name);
    const list = byLane.get(kind);
    if (list) list.push(name);
    else byLane.set(kind, [name]);
  }

  // Assign each node a (column, row), wrapping tall columns and advancing the
  // column whenever the dependency depth increases (so chains read left→right).
  const placement = new Map<string, { col: number; row: number }>();
  let laneBaseCol = 0;
  for (const lane of LANE_ORDER) {
    const names = byLane.get(lane);
    if (!names || names.length === 0) continue;

    const sorted = [...names].sort(
      (a, b) =>
        (depth.get(a) ?? 0) - (depth.get(b) ?? 0) ||
        (orderIndex.get(a) ?? 0) - (orderIndex.get(b) ?? 0),
    );

    let subCol = 0;
    let row = 0;
    let prevDepth: number | null = null;
    for (const name of sorted) {
      const d = depth.get(name) ?? 0;
      if (prevDepth !== null) {
        if (d !== prevDepth) {
          subCol += 1;
          row = 0;
        } else if (row >= MAX_ROWS) {
          subCol += 1;
          row = 0;
        }
      }
      placement.set(name, { col: laneBaseCol + subCol, row });
      row += 1;
      prevDepth = d;
    }
    laneBaseCol += subCol + 1;
  }

  const colCounts = new Map<number, number>();
  for (const { col } of placement.values()) {
    colCounts.set(col, (colCounts.get(col) ?? 0) + 1);
  }
  const maxRows = Math.max(1, ...colCounts.values());

  const nodes: Node[] = graph.nodes.map((name) => {
    const p = placement.get(name) ?? { col: 0, row: 0 };
    const count = colCounts.get(p.col) ?? 1;
    const yOffset = ((maxRows - count) * ROW_HEIGHT) / 2;
    return {
      id: name,
      type: "pipeline",
      position: { x: p.col * COL_WIDTH, y: yOffset + p.row * ROW_HEIGHT },
      data: { label: name, kind: tableKind(name) },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
    };
  });

  return { nodes, edges };
}

function computeDepths(graph: GraphResponse): Map<string, number> {
  const depth = new Map<string, number>();
  for (const name of graph.nodes) depth.set(name, 0);

  const order = graph.execution_order;
  if (!order || graph.cycle_detected) {
    // No topological order available — spread nodes by a stable index heuristic.
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
