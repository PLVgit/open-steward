import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, GitBranch, Loader2 } from "lucide-react";

import { Panel, PanelBody } from "@/components/ui/panel";
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
  const [jobNames, setJobNames] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    let cancelled = false;
    setState({ state: "loading" });
    setJobNames(new Map());
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
    // Pipeline names enrich the edge inspector. Failures are non-fatal — the
    // inspector simply omits the name.
    api
      .listPipelines(configFile)
      .then((jobs) => {
        if (!cancelled) setJobNames(new Map(jobs.map((j) => [j.config_key, j.pipeline_name])));
      })
      .catch(() => {
        /* inspector shows config_key only */
      });
    return () => {
      cancelled = true;
    };
  }, [configFile]);

  const elements = useMemo(
    () => (state.state === "ok" ? buildFlowElements(state.graph) : null),
    [state],
  );

  const isEmpty = state.state === "ok" && state.graph.nodes.length === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-sm border border-border bg-card text-primary">
          <GitBranch className="h-5 w-5" />
        </div>
        <div>
          <p className="eyebrow">Topology</p>
          <h1 className="text-xl font-bold uppercase tracking-tight">Pipeline Graph</h1>
          <p className="techmeta mt-1 normal-case">
            Table dependencies and execution order from{" "}
            <code className="text-foreground/80">{configFile}</code> · edges are labeled with the
            ETL config key
          </p>
        </div>
      </div>

      {state.state === "ok" && state.graph.cycle_detected && (
        <Panel accent="error">
          <PanelBody className="space-y-1">
            <p className="flex items-center gap-2 text-sm font-semibold text-destructive">
              <AlertTriangle className="h-4 w-4" /> Cycle detected
            </p>
            <p className="text-sm text-muted-foreground">
              The pipeline has a circular dependency, so no execution order can be determined.
              Nodes are shown in a fallback layout.
            </p>
          </PanelBody>
        </Panel>
      )}

      {state.state === "loading" && (
        <Panel className="flex h-[60vh] items-center justify-center">
          <PanelBody className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading graph…
          </PanelBody>
        </Panel>
      )}

      {state.state === "error" && (
        <Panel accent="error">
          <PanelBody className="flex items-center gap-2 text-sm text-destructive" role="alert">
            <AlertTriangle className="h-4 w-4 shrink-0" /> {state.message}
          </PanelBody>
        </Panel>
      )}

      {isEmpty && (
        <Panel>
          <PanelBody className="py-10 text-center text-sm text-muted-foreground">
            No tables found in this config.
          </PanelBody>
        </Panel>
      )}

      {state.state === "ok" && elements && !isEmpty && (
        <PipelineFlow nodes={elements.nodes} edges={elements.edges} jobNames={jobNames} />
      )}
    </div>
  );
}
