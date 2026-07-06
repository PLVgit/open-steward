import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Panel,
  Position,
  ReactFlow,
} from "@xyflow/react";
import type { Edge, Node, NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type { TableKind } from "@/lib/graphLayout";
import { cn } from "@/lib/utils";

interface PipelineFlowProps {
  nodes: Node[];
  edges: Edge[];
  /** Optional config_key → pipeline_name map to enrich the edge inspector. */
  jobNames?: Map<string, string>;
}

// Styling per table category. `mini` is the solid color used by the minimap.
const KIND: Record<TableKind, { label: string; bar: string; dot: string; tag: string; mini: string }> = {
  source: {
    label: "Source / raw",
    bar: "bg-emerald-400",
    dot: "bg-emerald-400",
    tag: "text-emerald-300",
    mini: "#34d399",
  },
  staging: {
    label: "Staging",
    bar: "bg-sky-400",
    dot: "bg-sky-400",
    tag: "text-sky-300",
    mini: "#38bdf8",
  },
  mart: {
    label: "Mart",
    bar: "bg-violet-400",
    dot: "bg-violet-400",
    tag: "text-violet-300",
    mini: "#a78bfa",
  },
  unknown: {
    label: "Other",
    bar: "bg-slate-400",
    dot: "bg-slate-400",
    tag: "text-slate-300",
    mini: "#94a3b8",
  },
};

const ACCENT = "hsl(142 84% 52%)"; // neon green — active/selected
const EDGE_IDLE = "hsl(0 0% 36%)";

function PipelineNode({ data, selected }: NodeProps) {
  const label = String((data as { label?: string }).label ?? "");
  const kind = ((data as { kind?: TableKind }).kind ?? "unknown") as TableKind;
  const active = selected || Boolean((data as { active?: boolean }).active);
  const style = KIND[kind];
  const [schema, ...rest] = label.split(".");
  const table = rest.join(".") || schema;
  const hasSchema = rest.length > 0;

  return (
    <div
      className={cn(
        "relative flex w-[236px] items-stretch overflow-hidden rounded-sm border bg-card shadow-lg transition-shadow",
        active
          ? "border-primary shadow-[0_0_0_1px_hsl(142_84%_52%),0_0_22px_-6px_hsl(142_84%_52%/0.7)]"
          : "border-border shadow-black/50",
      )}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2 !w-2 !border-0 !bg-muted-foreground/60"
      />
      <div className={cn("w-1 shrink-0", style.bar)} />
      <div className="min-w-0 flex-1 px-3 py-2">
        <div className="flex items-center gap-1.5">
          <span className={cn("h-1.5 w-1.5 rounded-full", style.dot)} />
          <span className={cn("truncate text-[10px] font-semibold uppercase tracking-wide", style.tag)}>
            {hasSchema ? schema : style.label}
          </span>
        </div>
        <div className="mt-0.5 truncate font-mono text-[13px] font-medium text-foreground" title={label}>
          {table}
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !border-0 !bg-muted-foreground/60"
      />
    </div>
  );
}

const nodeTypes = { pipeline: PipelineNode };

const defaultEdgeOptions = {
  type: "smoothstep",
  markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: "hsl(0 0% 50%)" },
  style: { stroke: EDGE_IDLE, strokeWidth: 1.5 },
  labelShowBg: true,
  labelBgPadding: [6, 3] as [number, number],
  labelBgBorderRadius: 3,
  labelStyle: { fontSize: 11, fontFamily: "ui-monospace, SFMono-Regular, monospace", fill: "hsl(142 84% 70%)" },
  labelBgStyle: { fill: "hsl(0 0% 9%)", fillOpacity: 0.96, stroke: ACCENT, strokeWidth: 0.6 },
};

function LegendSwatch({ kind }: { kind: TableKind }) {
  return (
    <div className="flex items-center gap-2">
      <span className={cn("h-2.5 w-2.5 rounded-sm", KIND[kind].bar)} />
      <span className="text-muted-foreground">{KIND[kind].label}</span>
    </div>
  );
}

function InspectorRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="eyebrow shrink-0">{label}</span>
      <span className="truncate font-mono text-xs text-foreground" title={value}>
        {value}
      </span>
    </div>
  );
}

type Selection =
  | { kind: "edge"; id: string }
  | { kind: "node"; id: string }
  | null;

/**
 * React Flow canvas for the pipeline graph. Isolated in its own module so the
 * page stays readable and so tests can mock this component instead of mounting
 * the full canvas (which needs DOM measurement unavailable in jsdom).
 *
 * Edge labels (config keys) are hidden by default to keep the canvas clean.
 * Hovering an edge previews its key; selecting an edge or a node reveals the
 * relevant keys and opens an inspector panel with the dependency details.
 */
export function PipelineFlow({ nodes, edges, jobNames }: PipelineFlowProps) {
  const [selection, setSelection] = useState<Selection>(null);
  const [hoverEdgeId, setHoverEdgeId] = useState<string | null>(null);
  const [hoverNodeId, setHoverNodeId] = useState<string | null>(null);

  // Escape clears the selection (focus mode off) from anywhere on the page.
  useEffect(() => {
    if (!selection) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelection(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selection]);

  const degree = useMemo(() => {
    const m = new Map<string, { in: number; out: number }>();
    for (const n of nodes) m.set(n.id, { in: 0, out: 0 });
    for (const e of edges) {
      const s = m.get(e.source);
      if (s) s.out += 1;
      const t = m.get(e.target);
      if (t) t.in += 1;
    }
    return m;
  }, [nodes, edges]);

  // Which edges should be highlighted + show their label right now.
  const activeEdgeIds = useMemo(() => {
    const ids = new Set<string>();
    if (hoverEdgeId) ids.add(hoverEdgeId);
    if (selection?.kind === "edge") ids.add(selection.id);
    const focusNode = selection?.kind === "node" ? selection.id : hoverNodeId;
    if (focusNode) {
      for (const e of edges) {
        if (e.source === focusNode || e.target === focusNode) ids.add(e.id);
      }
    }
    return ids;
  }, [edges, selection, hoverEdgeId, hoverNodeId]);

  // Focus mode: when a node is selected, everything unrelated dims so its
  // neighborhood reads instantly. Escape or clicking the canvas clears it.
  const focusNodeIds = useMemo(() => {
    if (selection?.kind !== "node") return null;
    const ids = new Set<string>([selection.id]);
    for (const e of edges) {
      if (e.source === selection.id) ids.add(e.target);
      if (e.target === selection.id) ids.add(e.source);
    }
    return ids;
  }, [edges, selection]);

  const styledEdges = useMemo<Edge[]>(
    () =>
      edges.map((e) => {
        const active = activeEdgeIds.has(e.id);
        const dimmed = focusNodeIds !== null && !active;
        return {
          ...e,
          label: active ? e.label : undefined,
          animated: active,
          zIndex: active ? 1000 : 0,
          style: {
            stroke: active ? ACCENT : EDGE_IDLE,
            strokeWidth: active ? 2 : 1.5,
            opacity: dimmed ? 0.18 : 1,
            transition: "opacity 0.15s ease",
          },
          markerEnd: {
            type: MarkerType.ArrowClosed,
            width: 14,
            height: 14,
            color: active ? ACCENT : "hsl(0 0% 50%)",
          },
        };
      }),
    [edges, activeEdgeIds, focusNodeIds],
  );

  const styledNodes = useMemo<Node[]>(
    () =>
      nodes.map((n) => ({
        ...n,
        selected: selection?.kind === "node" && selection.id === n.id,
        style: {
          opacity: focusNodeIds !== null && !focusNodeIds.has(n.id) ? 0.25 : 1,
          transition: "opacity 0.15s ease",
        },
      })),
    [nodes, selection, focusNodeIds],
  );

  // Resolve the current selection into inspector fields from the graph payload.
  const inspector = useMemo(() => {
    if (selection?.kind === "edge") {
      const e = edges.find((x) => x.id === selection.id);
      if (!e) return null;
      const configKey =
        (e.data as { configKey?: string } | undefined)?.configKey ?? String(e.label ?? "");
      const pipelineName = jobNames?.get(configKey);
      return {
        kind: "edge" as const,
        title: "Dependency",
        rows: [
          { label: "config_key", value: configKey },
          ...(pipelineName ? [{ label: "pipeline", value: pipelineName }] : []),
          { label: "source", value: e.source },
          { label: "target", value: e.target },
        ],
      };
    }
    if (selection?.kind === "node") {
      const n = nodes.find((x) => x.id === selection.id);
      if (!n) return null;
      const kind = ((n.data as { kind?: TableKind }).kind ?? "unknown") as TableKind;
      const d = degree.get(n.id) ?? { in: 0, out: 0 };
      return {
        kind: "node" as const,
        title: "Table",
        rows: [
          { label: "table", value: n.id },
          { label: "namespace", value: KIND[kind].label },
          { label: "incoming", value: String(d.in) },
          { label: "outgoing", value: String(d.out) },
        ],
      };
    }
    return null;
  }, [selection, edges, nodes, degree, jobNames]);

  return (
    <div className="h-[calc(100vh-11rem)] min-h-[540px] w-full overflow-hidden rounded-sm border border-border bg-card/50">
      <ReactFlow
        nodes={styledNodes}
        edges={styledEdges}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable
        onEdgeMouseEnter={(_, edge) => setHoverEdgeId(edge.id)}
        onEdgeMouseLeave={() => setHoverEdgeId(null)}
        onNodeMouseEnter={(_, node) => setHoverNodeId(node.id)}
        onNodeMouseLeave={() => setHoverNodeId(null)}
        onEdgeClick={(_, edge) => setSelection({ kind: "edge", id: edge.id })}
        onNodeClick={(_, node) => setSelection({ kind: "node", id: node.id })}
        onPaneClick={() => setSelection(null)}
        proOptions={{ hideAttribution: false }}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="hsl(0 0% 20%)" />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          maskColor="hsl(0 0% 4% / 0.74)"
          style={{ background: "hsl(0 0% 8%)" }}
          nodeColor={(n) => KIND[((n.data as { kind?: TableKind }).kind ?? "unknown") as TableKind].mini}
          nodeStrokeWidth={0}
        />

        <Panel position="top-left">
          <div className="glass-panel flex flex-col gap-1.5 rounded-sm px-3 py-2 text-xs shadow-lg">
            <div className="eyebrow mb-1">Table types</div>
            <LegendSwatch kind="source" />
            <LegendSwatch kind="staging" />
            <LegendSwatch kind="mart" />
            <LegendSwatch kind="unknown" />
          </div>
        </Panel>

        <Panel position="top-right">
          {inspector ? (
            <div className="glass-panel w-60 rounded-sm px-3 py-2.5 shadow-lg">
              <div className="eyebrow mb-2 border-b border-border pb-1.5">{inspector.title}</div>
              <div className="space-y-1.5">
                {inspector.rows.map((r) => (
                  <InspectorRow key={r.label} label={r.label} value={r.value} />
                ))}
              </div>
              {inspector.kind === "node" && selection?.kind === "node" && (
                <Link
                  to={`/profile?table=${encodeURIComponent(selection.id)}`}
                  className="mt-2.5 flex items-center justify-center rounded-sm border border-primary/40 bg-primary/10 px-2 py-1.5 font-mono text-[11px] font-semibold uppercase tracking-wide text-primary transition-colors hover:bg-primary/20"
                >
                  Profile this table →
                </Link>
              )}
              <div className="techmeta mt-2 normal-case text-[10px]">Esc to clear</div>
            </div>
          ) : (
            <div className="glass-panel rounded-sm px-3 py-2 text-[11px] text-muted-foreground shadow-lg">
              Hover an edge · click an edge or table to inspect
            </div>
          )}
        </Panel>
      </ReactFlow>
    </div>
  );
}
