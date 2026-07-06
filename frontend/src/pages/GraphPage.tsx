import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, GitBranch, ListOrdered, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { PipelineFlow } from "@/components/graph/PipelineFlow";
import { api, ApiError } from "@/lib/api";
import { buildFlowElements } from "@/lib/graphLayout";
import { useConfig } from "@/context/ConfigContext";
import type { GraphResponse } from "@/lib/types";

type State =
  | { state: "loading" }
  | { state: "ok"; graph: GraphResponse }
  | { state: "error"; message: string };

/** Collapsible numbered rail showing the computed execution order. */
function ExecutionOrder({ order }: { order: string[] }) {
  const [open, setOpen] = useState(false);
  return (
    <Panel>
      <PanelHeader>
        <div className="flex min-w-0 items-center gap-2">
          <ListOrdered className="h-4 w-4 shrink-0 text-primary" />
          <span className="text-sm font-semibold tracking-tight">Execution order</span>
          <span className="techmeta normal-case">{order.length} steps</span>
        </div>
        <Button size="sm" variant="ghost" onClick={() => setOpen((o) => !o)}>
          {open ? (
            <>
              Hide <ChevronUp className="h-3.5 w-3.5" />
            </>
          ) : (
            <>
              Show <ChevronDown className="h-3.5 w-3.5" />
            </>
          )}
        </Button>
      </PanelHeader>
      {open && (
        <PanelBody className="flex flex-wrap gap-1.5">
          {order.map((table, i) => (
            <span
              key={table}
              className="surface-inset inline-flex items-center gap-1.5 px-2 py-1 font-mono text-xs"
            >
              <span className="font-bold tabular-nums text-primary">{i + 1}</span>
              <span className="text-foreground/90">{table}</span>
            </span>
          ))}
        </PanelBody>
      )}
    </Panel>
  );
}

export function GraphPage() {
  const { configFile } = useConfig();
  const [state, setState] = useState<State>({ state: "loading" });
  const [jobNames, setJobNames] = useState<Map<string, string>>(new Map());
  const [reloadKey, setReloadKey] = useState(0);

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
  }, [configFile, reloadKey]);

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
            <code className="text-foreground/80">{configFile}</code> · hover or select edges and
            tables to inspect
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

      {state.state === "ok" &&
        !state.graph.cycle_detected &&
        (state.graph.execution_order?.length ?? 0) > 0 && (
          <ExecutionOrder order={state.graph.execution_order!} />
        )}

      {state.state === "loading" && (
        <>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading graph…
          </p>
          <Skeleton className="h-[60vh] min-h-[540px]" aria-hidden />
        </>
      )}

      {state.state === "error" && (
        <ErrorState message={state.message} onRetry={() => setReloadKey((k) => k + 1)} />
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
