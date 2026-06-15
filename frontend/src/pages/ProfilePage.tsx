import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle, CheckCircle2, FileSearch, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusDot } from "@/components/ui/status-dot";
import { api, ApiError } from "@/lib/api";
import { dash, pct } from "@/lib/statistics";
import { cn } from "@/lib/utils";
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

const SEVERITY_RAIL: Record<Severity, string> = {
  error: "border-l-destructive",
  warning: "border-l-amber-400",
  info: "border-l-sky-400",
};

const SEVERITY_DOT: Record<Severity, "error" | "warning" | "info"> = {
  error: "error",
  warning: "warning",
  info: "info",
};

function hasText(value: string | null): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function SummaryStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="surface-inset px-4 py-2.5">
      {/* label then value: the test reads label.nextElementSibling as the value */}
      <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 font-mono text-sm font-medium text-foreground">{value}</div>
    </div>
  );
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
      <div className="flex items-start gap-3">
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-sm border border-border bg-card text-primary">
          <FileSearch className="h-5 w-5" />
        </div>
        <div>
          <p className="eyebrow">Data Quality</p>
          <h1 className="text-xl font-bold uppercase tracking-tight">Table Profile</h1>
          <p className="techmeta mt-1 normal-case">
            Per-column quality for a table in{" "}
            <code className="text-foreground/80">demo_data/</code> ·{" "}
            <span className="font-mono">—</span> means not computable (empty-string stats apply to
            text only), not zero
          </p>
        </div>
      </div>

      <Panel>
        <PanelBody className="py-3">
          <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-2">
            <span className="eyebrow">Target table</span>
            <input
              aria-label="Table name"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="h-9 w-72 rounded-sm border border-input bg-background px-3 font-mono text-sm text-foreground outline-none transition focus:border-primary focus:ring-1 focus:ring-primary/40"
            />
            <Button type="submit" size="sm">
              Profile
            </Button>
          </form>
        </PanelBody>
      </Panel>

      {state.state === "loading" && (
        <Panel>
          <PanelBody className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading profile…
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

      {profile && (
        <>
          <div className="grid grid-cols-3 gap-3">
            <SummaryStat label="table" value={profile.table_name} />
            <SummaryStat label="rows" value={profile.row_count} />
            <SummaryStat label="columns" value={profile.column_count} />
          </div>

          {profile.columns.length === 0 ? (
            <p className="text-sm text-muted-foreground">No profileable columns.</p>
          ) : (
            <Panel>
              <PanelHeader eyebrow="Columns" title="Per-column profile" right={`${profile.columns.length} cols`} />
              <div className="overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="border-b border-border bg-white/[0.015] text-left text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                      <th className="px-4 py-2 font-semibold">column</th>
                      <th className="px-4 py-2 font-semibold">dtype</th>
                      <th className="px-4 py-2 font-semibold">nulls</th>
                      <th className="px-4 py-2 font-semibold">null %</th>
                      <th className="px-4 py-2 font-semibold">distinct</th>
                      <th className="px-4 py-2 font-semibold">distinct %</th>
                      <th className="px-4 py-2 font-semibold">empty</th>
                      <th className="px-4 py-2 font-semibold">empty %</th>
                    </tr>
                  </thead>
                  <tbody className="font-mono tabular-nums">
                    {profile.columns.map((c) => {
                      const highNull = c.null_pct >= 20;
                      const highEmpty = c.empty_string_pct != null && c.empty_string_pct >= 10;
                      return (
                        <tr
                          key={c.column_name}
                          className="border-b border-border/60 last:border-0 hover:bg-accent"
                        >
                          <td className="px-4 py-2 text-foreground">{c.column_name}</td>
                          <td className="px-4 py-2 text-muted-foreground">{c.dtype}</td>
                          <td className="px-4 py-2">{c.null_count}</td>
                          <td className={cn("px-4 py-2", highNull && "text-amber-300")}>{pct(c.null_pct)}</td>
                          <td className="px-4 py-2">{c.distinct_count}</td>
                          <td className="px-4 py-2">{pct(c.distinct_pct)}</td>
                          <td className="px-4 py-2">{dash(c.empty_string_count)}</td>
                          <td className={cn("px-4 py-2", highEmpty && "text-amber-300")}>{pct(c.empty_string_pct)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          <FindingsList findings={findings} />
        </>
      )}
    </div>
  );
}

function FindingsList({ findings }: { findings: ValidationFinding[] }) {
  if (findings.length === 0) {
    return (
      <Panel accent="healthy">
        <PanelBody className="flex items-center gap-2 text-sm text-primary">
          <CheckCircle2 className="h-4 w-4" /> No data quality findings. ✓
        </PanelBody>
      </Panel>
    );
  }
  return (
    <Panel>
      <PanelHeader eyebrow="Issues" title="Data quality findings" right={`${findings.length} found`} />
      <ul className="divide-y divide-border">
        {findings.map((f, i) => (
          <li
            key={`${f.finding_type}-${f.affected_table ?? ""}-${i}`}
            className={cn("space-y-1.5 border-l-2 px-4 py-3", SEVERITY_RAIL[f.severity])}
          >
            <div className="flex flex-wrap items-center gap-2">
              <StatusDot status={SEVERITY_DOT[f.severity]} />
              <Badge variant={SEVERITY_VARIANT[f.severity]}>{f.severity.toUpperCase()}</Badge>
              <span className="font-mono text-sm font-medium text-foreground">{f.finding_type}</span>
            </div>
            <p className="text-sm leading-relaxed">{f.message}</p>
            {hasText(f.recommendation) && (
              <p className="text-sm text-muted-foreground">→ {f.recommendation}</p>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
