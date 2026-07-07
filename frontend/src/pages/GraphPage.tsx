import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp, GitBranch, ListOrdered, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";
import { PipelineFlow } from "@/components/graph/PipelineFlow";
import { api, ApiError } from "@/lib/api";
import { buildFlowElements, filterGraph, hiddenTables } from "@/lib/graphLayout";
import { useConfig } from "@/context/ConfigContext";
import type { GraphResponse, PipelineJob } from "@/lib/types";

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
  const [jobs, setJobs] = useState<PipelineJob[]>([]);
  const [showHidden, setShowHidden] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ state: "loading" });
    setJobs([]);
    setShowHidden(false);
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
    // Jobs enrich the edge inspector (names) and drive hide_from_graph
    // filtering. Failures are non-fatal — the graph shows everything.
    api
      .listPipelines(configFile)
      .then((js) => {
        if (!cancelled && Array.isArray(js)) setJobs(js);
      })
      .catch(() => {
        /* inspector shows config_key only; nothing hidden */
      });
    return () => {
      cancelled = true;
    };
  }, [configFile, reloadKey]);

  const jobNames = useMemo(
    () => new Map(jobs.map((j) => [j.config_key, j.pipeline_name])),
    [jobs],
  );
  // Tables tagged hide_from_graph — a visibility concern only; the analysis
  // pages still include them.
  const hidden = useMemo(() => hiddenTables(jobs), [jobs]);

  const elements = useMemo(
    () =>
      state.state === "ok"
        ? buildFlowElements(filterGraph(state.graph, showHidden ? new Set<string>() : hidden))
        : null,
    [state, hidden, showHidden],
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

      {state.state === "ok" && hidden.size > 0 && (
        <div className="flex items-center justify-between gap-3 rounded-sm border border-border bg-card px-3 py-2">
          <span className="flex items-center gap-2 text-xs text-muted-foreground">
            <StatusDot status="idle" />
            {hidden.size} table{hidden.size === 1 ? "" : "s"} tagged{" "}
            <code className="font-mono text-foreground/80">hide_from_graph</code>
            {showHidden ? " (shown)" : ""}
          </span>
          <Button size="sm" variant="ghost" onClick={() => setShowHidden((v) => !v)}>
            {showHidden ? "Hide hidden" : "Show hidden"}
          </Button>
        </div>
      )}

      {state.state === "ok" && elements && !isEmpty && (
        <PipelineFlow nodes={elements.nodes} edges={elements.edges} jobNames={jobNames} />
      )}
    </div>
  );
}
