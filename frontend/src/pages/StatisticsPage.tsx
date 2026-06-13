import { useEffect, useMemo, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { boolText, dash, pct, summarizeStatistics } from "@/lib/statistics";
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
    tone === "amber" ? "text-amber-500" : tone === "red" ? "text-destructive" : "";
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={`font-mono text-sm ${toneClass}`}>{value}</div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="py-4">
        <div className="text-2xl font-semibold">{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </CardContent>
    </Card>
  );
}

export function StatisticsPage() {
  const { configFile } = useConfig();
  const [state, setState] = useState<State>({ state: "loading" });

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
  }, [configFile]);

  const stats = state.state === "ok" ? state.stats : [];
  const summary = useMemo(() => summarizeStatistics(stats), [stats]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>ETL Statistics</CardTitle>
          <CardDescription>
            Per-job source/target metrics for{" "}
            <code className="font-mono">{configFile}</code>. <span className="font-mono">—</span>{" "}
            means the value is not computable or the data is missing (a missing source/target
            table, or no primary key) — it does not mean zero.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {state.state === "loading" && (
            <p className="text-sm text-muted-foreground">Loading statistics…</p>
          )}
          {state.state === "error" && (
            <p className="text-sm text-destructive" role="alert">
              {state.message}
            </p>
          )}
          {state.state === "ok" && stats.length === 0 && (
            <p className="text-sm text-muted-foreground">
              No enabled jobs with statistics.
            </p>
          )}
        </CardContent>
      </Card>

      {state.state === "ok" && stats.length > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <SummaryCard label="jobs with statistics" value={summary.total} />
            <SummaryCard label="jobs with row loss" value={summary.withRowLoss} />
            <SummaryCard label="jobs with missing data" value={summary.withMissingData} />
            <SummaryCard label="jobs with PK issues" value={summary.withPkIssues} />
          </div>

          {stats.map((s) => {
            const rowLoss = s.lost_rows != null && s.lost_rows > 0;
            const pkIssue =
              (s.primary_key_null_count ?? 0) > 0 ||
              (s.primary_key_duplicate_count ?? 0) > 0;
            return (
              <Card key={s.config_key}>
                <CardHeader>
                  <CardTitle className="text-base">
                    <span className="font-mono">{s.config_key}</span>{" "}
                    <span className="font-normal text-muted-foreground">
                      — {s.pipeline_name}
                    </span>
                  </CardTitle>
                  <CardDescription className="font-mono text-xs">
                    {s.source_table} → {s.target_table}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
                    <Metric label="source_count" value={dash(s.source_count)} />
                    <Metric label="target_count" value={dash(s.target_count)} />
                    <Metric
                      label="lost_rows"
                      value={dash(s.lost_rows)}
                      tone={rowLoss ? "amber" : undefined}
                    />
                    <Metric
                      label="loss_pct"
                      value={pct(s.loss_pct)}
                      tone={rowLoss ? "amber" : undefined}
                    />
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
                  {(rowLoss || pkIssue) && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      {rowLoss && "Row loss detected. "}
                      {pkIssue && "Primary-key quality issue detected."}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </>
      )}
    </div>
  );
}
