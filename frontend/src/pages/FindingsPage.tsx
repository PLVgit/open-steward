import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, CheckCircle2, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";
import { api, ApiError } from "@/lib/api";
import {
  filterBySeverity,
  sortBySeverity,
  summarizeFindings,
  type SeverityFilter,
} from "@/lib/findings";
import { cn } from "@/lib/utils";
import { useConfig } from "@/context/ConfigContext";
import type { Severity, ValidationFinding } from "@/lib/types";

type State =
  | { state: "loading" }
  | { state: "ok"; findings: ValidationFinding[] }
  | { state: "error"; message: string };

const SEVERITY_VARIANT: Record<Severity, "error" | "warning" | "info"> = {
  error: "error",
  warning: "warning",
  info: "info",
};

const SEVERITY_RAIL: Record<Severity, string> = {
  error: "border-l-destructive",
  warning: "border-l-amber-400",
  info: "border-l-sky-400",
};

// Subtle surface tint so the severity mix is scannable (errors heaviest).
const SEVERITY_SURFACE: Record<Severity, string> = {
  error: "bg-destructive/[0.06]",
  warning: "bg-amber-400/[0.04]",
  info: "bg-transparent",
};

const SEVERITY_DOT: Record<Severity, "error" | "warning" | "info"> = {
  error: "error",
  warning: "warning",
  info: "info",
};

// Findings produced by the transformation-aware reconciliation engine — these
// are Open Steward's headline capability, so we highlight them.
const TRANSFORM_TYPES = new Set([
  "row_loss_explained_by_filter",
  "unexpected_row_loss",
  "row_count_change_explained_by_transformations",
  "unexpected_row_loss_after_join",
  "unexpected_row_surplus_after_join",
  "join_unmatched_rows",
  "join_key_nulls",
  "possible_row_multiplication",
  "possible_many_to_many_join",
]);

const FILTERS: { value: SeverityFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "error", label: "Errors" },
  { value: "warning", label: "Warnings" },
  { value: "info", label: "Info" },
];

function hasText(value: string | null): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function SummaryChip({
  count,
  noun,
  tone,
}: {
  count: number;
  noun: string;
  tone: "error" | "warning" | "info";
}) {
  const cls =
    tone === "error"
      ? "text-destructive ring-destructive/30 bg-destructive/10"
      : tone === "warning"
        ? "text-amber-300 ring-amber-400/30 bg-amber-400/10"
        : "text-sky-300 ring-sky-400/30 bg-sky-400/10";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 font-mono text-xs font-semibold ring-1 ring-inset",
        cls,
      )}
    >
      <StatusDot status={tone} />
      {count} {noun}
    </span>
  );
}

export function FindingsPage() {
  const { configFile } = useConfig();
  const [state, setState] = useState<State>({ state: "loading" });
  const [filter, setFilter] = useState<SeverityFilter>("all");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ state: "loading" });
    api
      // Request reconciliation findings too, using the default demo data
      // directory — keeps the dashboard consistent with the Statistics page.
      .getFindings(configFile, ".")
      .then((findings) => {
        if (!cancelled) setState({ state: "ok", findings });
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
  }, [configFile, reloadKey]);

  const findings = state.state === "ok" ? state.findings : [];
  const summary = useMemo(() => summarizeFindings(findings), [findings]);
  // Errors surface first — matches the CLI's severity-grouped output.
  const visible = useMemo(
    () => sortBySeverity(filterBySeverity(findings, filter)),
    [findings, filter],
  );

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-sm border border-border bg-card text-primary">
          <Activity className="h-5 w-5" />
        </div>
        <div>
          <p className="eyebrow">Alert Feed</p>
          <h1 className="text-xl font-bold uppercase tracking-tight">Findings</h1>
          <p className="techmeta mt-1 normal-case">
            Structural, SQL and reconciliation checks for{" "}
            <code className="text-foreground/80">{configFile}</code> · reconciliation reads{" "}
            <code className="text-foreground/80">demo_data/</code>
          </p>
        </div>
      </div>

      {state.state === "loading" && (
        <>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading findings…
          </p>
          <div className="space-y-3" aria-hidden>
            <div className="flex gap-2">
              <Skeleton className="h-7 w-24" />
              <Skeleton className="h-7 w-28" />
              <Skeleton className="h-7 w-20" />
            </div>
            <Skeleton className="h-72" />
          </div>
        </>
      )}
      {state.state === "error" && (
        <ErrorState message={state.message} onRetry={() => setReloadKey((k) => k + 1)} />
      )}

      {state.state === "ok" && (
        <div className="flex flex-wrap items-center gap-2">
          <SummaryChip count={summary.error} noun="errors" tone="error" />
          <SummaryChip count={summary.warning} noun="warnings" tone="warning" />
          <SummaryChip count={summary.info} noun="info" tone="info" />
          <span className="techmeta normal-case">· {summary.total} total</span>
        </div>
      )}

      {state.state === "ok" && summary.total > 0 && (
        <div className="flex flex-wrap gap-2">
          {FILTERS.map(({ value, label }) => (
            <Button
              key={value}
              size="sm"
              variant={filter === value ? "default" : "outline"}
              onClick={() => setFilter(value)}
            >
              {label}
            </Button>
          ))}
        </div>
      )}

      {state.state === "ok" && summary.total === 0 && (
        <Panel accent="healthy" className="shadow-[0_0_34px_-14px_hsl(142_84%_52%/0.5)]">
          <PanelBody className="flex flex-col items-center gap-2 py-12 text-center">
            <CheckCircle2 className="h-8 w-8 text-primary" />
            <p className="text-sm font-semibold text-primary">No findings. ✓</p>
            <p className="techmeta normal-case">All structural, SQL and reconciliation checks passed</p>
          </PanelBody>
        </Panel>
      )}

      {state.state === "ok" && visible.length > 0 && (
        <Panel>
          <PanelHeader
            eyebrow="Issues"
            title={filter === "all" ? "All findings" : `${filter} findings`}
            right={`${visible.length} shown`}
          />
          <ul className="divide-y divide-border">
            {visible.map((f, i) => {
              const isTransform = TRANSFORM_TYPES.has(f.finding_type);
              return (
                <li
                  key={`${f.finding_type}-${f.affected_job ?? ""}-${f.affected_table ?? ""}-${i}`}
                  className={cn(
                    "space-y-1.5 border-l-2 px-4 py-3",
                    SEVERITY_RAIL[f.severity],
                    SEVERITY_SURFACE[f.severity],
                  )}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusDot status={SEVERITY_DOT[f.severity]} />
                    <Badge variant={SEVERITY_VARIANT[f.severity]}>{f.severity.toUpperCase()}</Badge>
                    <span className="font-mono text-sm font-medium text-foreground">
                      {f.finding_type}
                    </span>
                    {isTransform && <Badge variant="success">transform</Badge>}
                    {hasText(f.affected_table) && (
                      <Link
                        to={`/profile?table=${encodeURIComponent(f.affected_table)}`}
                        title={`Profile ${f.affected_table}`}
                        className="font-mono text-xs text-muted-foreground underline decoration-border underline-offset-2 transition-colors hover:text-primary hover:decoration-primary"
                      >
                        {f.affected_table}
                      </Link>
                    )}
                    {hasText(f.affected_job) && (
                      <span className="techmeta normal-case">job: {f.affected_job}</span>
                    )}
                  </div>
                  <p className="text-sm leading-relaxed text-foreground/90">{f.message}</p>
                  {hasText(f.recommendation) && (
                    <p className="text-sm text-muted-foreground">→ {f.recommendation}</p>
                  )}
                </li>
              );
            })}
          </ul>
        </Panel>
      )}

      {state.state === "ok" && summary.total > 0 && visible.length === 0 && (
        <p className="text-sm text-muted-foreground">No findings match this filter.</p>
      )}
    </div>
  );
}
