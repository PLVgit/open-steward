import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import {
  filterBySeverity,
  summarizeFindings,
  type SeverityFilter,
} from "@/lib/findings";
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

const FILTERS: { value: SeverityFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "error", label: "Errors" },
  { value: "warning", label: "Warnings" },
  { value: "info", label: "Info" },
];

function hasText(value: string | null): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function FindingsPage() {
  const { configFile } = useConfig();
  const [state, setState] = useState<State>({ state: "loading" });
  const [filter, setFilter] = useState<SeverityFilter>("all");

  useEffect(() => {
    let cancelled = false;
    setState({ state: "loading" });
    api
      .getFindings(configFile)
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
  }, [configFile]);

  const findings = state.state === "ok" ? state.findings : [];
  const summary = useMemo(() => summarizeFindings(findings), [findings]);
  const visible = useMemo(() => filterBySeverity(findings, filter), [findings, filter]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Findings</CardTitle>
          <CardDescription>
            Structural and SQL findings for <code className="font-mono">{configFile}</code>.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {state.state === "loading" && (
            <p className="text-sm text-muted-foreground">Loading findings…</p>
          )}
          {state.state === "error" && (
            <p className="text-sm text-destructive" role="alert">
              {state.message}
            </p>
          )}
          {state.state === "ok" && (
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <span className="text-destructive">{summary.error} errors</span>
              <span className="text-amber-500">{summary.warning} warnings</span>
              <span className="text-sky-500">{summary.info} info</span>
              <span className="text-muted-foreground">· {summary.total} total</span>
            </div>
          )}
        </CardContent>
      </Card>

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
        <Card>
          <CardContent className="py-6">
            <p className="text-sm text-green-500">No findings. ✓</p>
          </CardContent>
        </Card>
      )}

      {state.state === "ok" &&
        visible.map((f, i) => (
          <Card key={`${f.finding_type}-${f.affected_job ?? ""}-${f.affected_table ?? ""}-${i}`}>
            <CardContent className="space-y-1 py-4">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={SEVERITY_VARIANT[f.severity]}>
                  {f.severity.toUpperCase()}
                </Badge>
                <span className="font-mono text-sm font-medium">{f.finding_type}</span>
                {hasText(f.affected_table) && (
                  <span className="font-mono text-xs text-muted-foreground">
                    {f.affected_table}
                  </span>
                )}
                {hasText(f.affected_job) && (
                  <span className="text-xs text-muted-foreground">job: {f.affected_job}</span>
                )}
              </div>
              <p className="text-sm">{f.message}</p>
              {hasText(f.recommendation) && (
                <p className="text-sm text-muted-foreground">→ {f.recommendation}</p>
              )}
            </CardContent>
          </Card>
        ))}

      {state.state === "ok" && summary.total > 0 && visible.length === 0 && (
        <p className="text-sm text-muted-foreground">No findings match this filter.</p>
      )}
    </div>
  );
}
