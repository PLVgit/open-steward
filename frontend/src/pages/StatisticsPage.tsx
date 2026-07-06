import { useEffect, useMemo, useState } from "react";
import { BarChart3, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/error-state";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { api, ApiError } from "@/lib/api";
import { boolText, dash, pct, summarizeStatistics } from "@/lib/statistics";
import { cn } from "@/lib/utils";
import { useConfig } from "@/context/ConfigContext";
import type { JobStatistics } from "@/lib/types";

type State =
  | { state: "loading" }
  | { state: "ok"; stats: JobStatistics[] }
  | { state: "error"; message: string };

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "amber" | "red";
}) {
  const toneClass =
    tone === "amber" ? "text-amber-300" : tone === "red" ? "text-destructive" : "text-foreground";
  return (
    <div className="surface-inset px-3 py-2">
      {/* label then value: the test reads label.nextElementSibling as the value */}
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </div>
      <div className={cn("mt-1 font-mono text-sm font-medium tabular-nums", toneClass)}>{value}</div>
    </div>
  );
}

function SummaryCard({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <Panel>
      <PanelBody className="py-4">
        {/* value then label: the test reads label.previousElementSibling as the value */}
        <div className={cn("font-mono text-3xl font-bold tabular-nums tracking-tight", tone)}>
          {value}
        </div>
        <div className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          {label}
        </div>
      </PanelBody>
    </Panel>
  );
}

export function StatisticsPage() {
  const { configFile } = useConfig();
  const [state, setState] = useState<State>({ state: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ state: "loading" });
    api
      .getStatistics(configFile)
      .then((stats) => {
        if (!cancelled) setState({ state: "ok", stats });
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

  const stats = state.state === "ok" ? state.stats : [];
  const summary = useMemo(() => summarizeStatistics(stats), [stats]);

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-sm border border-border bg-card text-primary">
          <BarChart3 className="h-5 w-5" />
        </div>
        <div>
          <p className="eyebrow">ETL Telemetry</p>
          <h1 className="text-xl font-bold uppercase tracking-tight">Statistics</h1>
          <p className="techmeta mt-1 normal-case">
            Per-job source/target metrics for{" "}
            <code className="text-foreground/80">{configFile}</code> ·{" "}
            <span className="font-mono">—</span> means not computable (missing table or key), not
            zero
          </p>
        </div>
      </div>

      {state.state === "loading" && (
        <>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading statistics…
          </p>
          <div className="space-y-3" aria-hidden>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-24" />
              ))}
            </div>
            <Skeleton className="h-44" />
            <Skeleton className="h-44" />
          </div>
        </>
      )}
      {state.state === "error" && (
        <ErrorState message={state.message} onRetry={() => setReloadKey((k) => k + 1)} />
      )}
      {state.state === "ok" && stats.length === 0 && (
        <Panel>
          <PanelBody className="py-8 text-center text-sm text-muted-foreground">
            No enabled jobs with statistics.
          </PanelBody>
        </Panel>
      )}

      {state.state === "ok" && stats.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <SummaryCard label="jobs with statistics" value={summary.total} />
            <SummaryCard
              label="jobs with row loss"
              value={summary.withRowLoss}
              tone={summary.withRowLoss > 0 ? "text-amber-300" : undefined}
            />
            <SummaryCard
              label="jobs with missing data"
              value={summary.withMissingData}
              tone={summary.withMissingData > 0 ? "text-muted-foreground" : undefined}
            />
            <SummaryCard
              label="jobs with PK issues"
              value={summary.withPkIssues}
              tone={summary.withPkIssues > 0 ? "text-destructive" : undefined}
            />
          </div>

          {stats.map((s) => {
            const rowLoss = s.lost_rows != null && s.lost_rows > 0;
            const pkIssue =
              (s.primary_key_null_count ?? 0) > 0 ||
              (s.primary_key_duplicate_count ?? 0) > 0;
            return (
              <Panel key={s.config_key} accent={pkIssue ? "error" : rowLoss ? "warning" : "none"}>
                <PanelHeader>
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-semibold text-foreground">
                      {s.config_key}
                    </span>
                    <span className="text-sm text-muted-foreground">— {s.pipeline_name}</span>
                    {rowLoss && <Badge variant="warning">row loss</Badge>}
                    {pkIssue && <Badge variant="error">pk issue</Badge>}
                  </div>
                  <div className="techmeta shrink-0 normal-case">
                    {s.source_table} → {s.target_table}
                  </div>
                </PanelHeader>
                <PanelBody>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                    <Metric label="source_count" value={dash(s.source_count)} />
                    <Metric label="target_count" value={dash(s.target_count)} />
                    <Metric label="lost_rows" value={dash(s.lost_rows)} tone={rowLoss ? "amber" : undefined} />
                    <Metric label="loss_pct" value={pct(s.loss_pct)} tone={rowLoss ? "amber" : undefined} />
                    <Metric label="target_empty" value={boolText(s.target_empty)} />
                    <Metric label="primary_key" value={s.primary_key ?? "—"} />
                    <Metric
                      label="pk_null_count"
                      value={dash(s.primary_key_null_count)}
                      tone={(s.primary_key_null_count ?? 0) > 0 ? "red" : undefined}
                    />
                    <Metric
                      label="pk_null_pct"
                      value={pct(s.primary_key_null_pct)}
                      tone={(s.primary_key_null_count ?? 0) > 0 ? "red" : undefined}
                    />
                    <Metric
                      label="pk_duplicate_count"
                      value={dash(s.primary_key_duplicate_count)}
                      tone={(s.primary_key_duplicate_count ?? 0) > 0 ? "red" : undefined}
                    />
                  </div>
                </PanelBody>
              </Panel>
            );
          })}
        </>
      )}
    </div>
  );
}
