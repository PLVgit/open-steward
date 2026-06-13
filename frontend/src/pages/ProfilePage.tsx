import { useEffect, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { dash, pct } from "@/lib/statistics";
import type { ProfileResponse, Severity, ValidationFinding } from "@/lib/types";

const DEFAULT_TABLE = "staging.orders";

type State =
  | { state: "loading" }
  | { state: "ok"; data: ProfileResponse }
  | { state: "error"; message: string };

const SEVERITY_VARIANT: Record<Severity, "error" | "warning" | "info"> = {
  error: "error",
  warning: "warning",
  info: "info",
};

function hasText(value: string | null): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

export function ProfilePage() {
  // `table` is the submitted value that drives the fetch; `input` is the live
  // text field. Two simple useState values — no state library.
  const [table, setTable] = useState(DEFAULT_TABLE);
  const [input, setInput] = useState(DEFAULT_TABLE);
  const [state, setState] = useState<State>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ state: "loading" });
    api
      .profileTable(table)
      .then((data) => {
        if (!cancelled) setState({ state: "ok", data });
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
  }, [table]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTable(input.trim());
  }

  const profile = state.state === "ok" ? state.data.profile : null;
  const findings = state.state === "ok" ? state.data.findings : [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Table Profile</CardTitle>
          <CardDescription>
            Per-column data quality for a table in <code className="font-mono">demo_data/</code>.{" "}
            <span className="font-mono">—</span> means the value is not computable (e.g.
            empty-string stats only apply to text columns) — it does not mean zero.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-2">
            <input
              aria-label="Table name"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="h-9 w-64 rounded-md border border-input bg-background px-2 font-mono text-sm"
            />
            <Button type="submit" size="sm">
              Profile
            </Button>
          </form>
        </CardContent>
      </Card>

      {state.state === "loading" && (
        <p className="text-sm text-muted-foreground">Loading profile…</p>
      )}
      {state.state === "error" && (
        <p className="text-sm text-destructive" role="alert">
          {state.message}
        </p>
      )}

      {profile && (
        <>
          <Card>
            <CardContent className="flex flex-wrap gap-6 py-4 text-sm">
              <div>
                <div className="text-xs text-muted-foreground">table</div>
                <div className="font-mono">{profile.table_name}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">rows</div>
                <div className="font-mono">{profile.row_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">columns</div>
                <div className="font-mono">{profile.column_count}</div>
              </div>
            </CardContent>
          </Card>

          {profile.columns.length === 0 ? (
            <p className="text-sm text-muted-foreground">No profileable columns.</p>
          ) : (
            <Card>
              <CardContent className="overflow-x-auto py-4">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-xs text-muted-foreground">
                      <th className="py-2 pr-4 font-medium">column</th>
                      <th className="py-2 pr-4 font-medium">dtype</th>
                      <th className="py-2 pr-4 font-medium">nulls</th>
                      <th className="py-2 pr-4 font-medium">null %</th>
                      <th className="py-2 pr-4 font-medium">distinct</th>
                      <th className="py-2 pr-4 font-medium">distinct %</th>
                      <th className="py-2 pr-4 font-medium">empty</th>
                      <th className="py-2 pr-4 font-medium">empty %</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono">
                    {profile.columns.map((c) => (
                      <tr key={c.column_name} className="border-b last:border-0">
                        <td className="py-2 pr-4">{c.column_name}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{c.dtype}</td>
                        <td className="py-2 pr-4">{c.null_count}</td>
                        <td className="py-2 pr-4">{pct(c.null_pct)}</td>
                        <td className="py-2 pr-4">{c.distinct_count}</td>
                        <td className="py-2 pr-4">{pct(c.distinct_pct)}</td>
                        <td className="py-2 pr-4">{dash(c.empty_string_count)}</td>
                        <td className="py-2 pr-4">{pct(c.empty_string_pct)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          )}

          <FindingsList findings={findings} />
        </>
      )}
    </div>
  );
}

function FindingsList({ findings }: { findings: ValidationFinding[] }) {
  if (findings.length === 0) {
    return <p className="text-sm text-green-500">No data quality findings. ✓</p>;
  }
  return (
    <div className="space-y-2">
      {findings.map((f, i) => (
        <Card key={`${f.finding_type}-${f.affected_table ?? ""}-${i}`}>
          <CardContent className="space-y-1 py-4">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={SEVERITY_VARIANT[f.severity]}>{f.severity.toUpperCase()}</Badge>
              <span className="font-mono text-sm font-medium">{f.finding_type}</span>
            </div>
            <p className="text-sm">{f.message}</p>
            {hasText(f.recommendation) && (
              <p className="text-sm text-muted-foreground">→ {f.recommendation}</p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
