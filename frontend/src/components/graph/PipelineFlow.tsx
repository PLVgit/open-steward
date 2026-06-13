import { Background, Controls, ReactFlow } from "@xyflow/react";
import type { Edge, Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

interface PipelineFlowProps {
  nodes: Node[];
  edges: Edge[];
}

/**
 * Thin wrapper around React Flow. Isolated in its own module so the page stays
 * readable and so tests can mock this component instead of mounting the full
 * React Flow canvas (which needs DOM measurement unavailable in jsdom).
 */
export function PipelineFlow({ nodes, edges }: PipelineFlowProps) {
  return (
    <div className="h-[600px] w-full rounded-lg border bg-card">
      <ReactFlow nodes={nodes} edges={edges} fitView nodesDraggable={false}>
        <Background />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
