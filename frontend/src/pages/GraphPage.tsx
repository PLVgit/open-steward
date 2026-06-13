import { useEffect, useMemo, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { PipelineFlow } from "@/components/graph/PipelineFlow";
import { api, ApiError } from "@/lib/api";
import { buildFlowElements } from "@/lib/graphLayout";
import { useConfig } from "@/context/ConfigContext";
import type { GraphResponse } from "@/lib/types";

type State =
  | { state: "loading" }
  | { state: "ok"; graph: GraphResponse }
  | { state: "error"; message: string };

export function GraphPage() {
  const { configFile } = useConfig();
  const [state, setState] = useState<State>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ state: "loading" });
    api
      .getGraph(configFile)
      .then((graph) => {
        if (!cancelled) setState({ state: "ok", graph });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError
            ? err.detail
            : "Could not reach the backend. Is it running on http://localhost:8000?";
        setState({ state: "error", message });
      });
    return () => {
      cancelled = true;
    };
  }, [configFile]);

  const elements = useMemo(
    () => (state.state === "ok" ? buildFlowElements(state.graph) : null),
    [state],
  );

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Pipeline Graph</CardTitle>
          <CardDescription>
            Table dependencies and execution order from{" "}
            <code className="font-mono">{configFile}</code>. Edges are labeled with the
            ETL config key that connects two tables.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {state.state === "loading" && (
            <p className="text-sm text-muted-foreground">Loading graph…</p>
          )}
          {state.state === "error" && (
            <p className="text-sm text-destructive" role="alert">
              {state.message}
            </p>
          )}
          {state.state === "ok" && state.graph.nodes.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No tables found in this config.
            </p>
          )}
        </CardContent>
      </Card>

      {state.state === "ok" && state.graph.cycle_detected && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive">Cycle detected</CardTitle>
            <CardDescription>
              The pipeline has a circular dependency, so no execution order can be
              determined. Nodes are shown in a fallback layout.
            </CardDescription>
          </CardHeader>
        </Card>
      )}

      {state.state === "ok" && elements && state.graph.nodes.length > 0 && (
        <PipelineFlow nodes={elements.nodes} edges={elements.edges} />
      )}
    </div>
  );
}
