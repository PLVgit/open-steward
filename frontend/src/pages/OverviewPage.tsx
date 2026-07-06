import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { ErrorState } from "@/components/ui/error-state";
import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { Skeleton } from "@/components/ui/skeleton";
import { StatusDot } from "@/components/ui/status-dot";
import { api, ApiError } from "@/lib/api";
import { summarizeFindings, type FindingsSummary } from "@/lib/findings";
import { summarizeStatistics, type StatisticsSummary } from "@/lib/statistics";
import { useCountUp } from "@/lib/useCountUp";
import { useConfig } from "@/context/ConfigContext";
import type { PipelineJob } from "@/lib/types";

type Status =
  | { state: "loading" }
  | { state: "ok"; jobs: PipelineJob[] }
  | { state: "error"; message: string };

/** A white instrument tile (black text), like the KPI cards on the reference
 *  console — high-contrast, big mono value, small mono footer. */
function Tile({
  label,
  value,
  footer,
  badge,
}: {
  label: string;
  value: ReactNode;
  footer: string;
  badge?: ReactNode;
}) {
  return (
    <div className="panel-in relative overflow-hidden rounded-sm border border-white/10 bg-white px-4 py-3.5 text-zinc-950 shadow-[0_10px_30px_-18px_rgb(0_0_0/0.9)]">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-zinc-500">
          {label}
        </span>
        {badge}
      </div>
      <div className="mt-2 font-mono text-3xl font-bold tabular-nums leading-none text-zinc-950">
        {value}
      </div>
      <div className="mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-zinc-400">
        {footer}
      </div>
    </div>
  );
}

/** Numeric tile value that counts up on mount (snaps under reduced motion). */
function CountUpValue({ value }: { value: number }) {
  return <>{useCountUp(value)}</>;
}

/** The single neon-green "headline status" tile (echoes the OPTIMAL card). */
function StatusTile({ label, value, footer }: { label: string; value: string; footer: string }) {
  return (
    <div className="panel-in relative overflow-hidden rounded-sm border border-primary/60 bg-primary/10 px-4 py-3.5 shadow-[0_0_34px_-12px_hsl(142_84%_52%/0.6)]">
      <span className="pointer-events-none absolute -right-6 -top-6 h-20 w-20 rounded-full bg-primary/30 blur-2xl" />
      <div className="relative flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-primary/80">
          {label}
        </span>
        <StatusDot status="healthy" pulse />
      </div>
      <div className="relative mt-2 font-mono text-3xl font-bold tracking-tight leading-none text-primary">
        {value}
      </div>
      <div className="relative mt-2 font-mono text-[10px] uppercase tracking-[0.12em] text-primary/70">
        {footer}
      </div>
    </div>
  );
}

/** A linked signal readout inside the Signals panel. */
function Signal({
  label,
  value,
  to,
  tone,
}: {
  label: string;
  value: number | undefined;
  to: string;
  tone: "error" | "warning" | "info" | "healthy";
}) {
  const valueTone =
    value === undefined
      ? "text-muted-foreground"
      : value > 0
        ? tone === "error"
          ? "text-destructive"
          : tone === "warning"
            ? "text-amber-300"
            : "text-sky-300"
        : "text-primary";
  return (
    <Link
      to={to}
      className="surface-inset group flex flex-col gap-1 px-3 py-2.5 transition-colors hover:border-primary/50 hover:bg-accent"
    >
      <span className="flex items-center justify-between">
        <span className="eyebrow">{label}</span>
        <StatusDot status={value === undefined ? "idle" : value > 0 ? tone : "healthy"} />
      </span>
      {value === undefined ? (
        <Skeleton className="h-7 w-10" />
      ) : (
        <span className={`font-mono text-2xl font-bold tabular-nums leading-none ${valueTone}`}>
          {value}
        </span>
      )}
    </Link>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-5" aria-hidden>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[104px]" />
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <Skeleton className="h-64 lg:col-span-2" />
        <div className="space-y-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-32" />
        </div>
      </div>
    </div>
  );
}

export function OverviewPage() {
  const { configFile } = useConfig();
  const [status, setStatus] = useState<Status>({ state: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [signals, setSignals] = useState<{
    findings?: FindingsSummary;
    stats?: StatisticsSummary;
  }>({});

  useEffect(() => {
    let cancelled = false;
    setStatus({ state: "loading" });
    setSignals({});
    api
      .listPipelines(configFile)
      .then((jobs) => {
        if (!cancelled) setStatus({ state: "ok", jobs });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError
            ? err.detail
            : "Could not reach the backend. Is it running on http://localhost:8000?";
        setStatus({ state: "error", message });
      });
    // Operational signals — independent, non-fatal fetches that turn the
    // Overview into a real command center. Failures just leave the skeletons.
    api
      .getFindings(configFile, ".")
      .then((fs) => {
        if (!cancelled) setSignals((p) => ({ ...p, findings: summarizeFindings(fs) }));
      })
      .catch(() => {});
    api
      .getStatistics(configFile)
      .then((st) => {
        if (!cancelled) setSignals((p) => ({ ...p, stats: summarizeStatistics(st) }));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [configFile, reloadKey]);

  const counts = useMemo(() => {
    if (status.state !== "ok") return { total: 0, enabled: 0, disabled: 0 };
    const enabled = status.jobs.filter((j) => j.enabled).length;
    return { total: status.jobs.length, enabled, disabled: status.jobs.length - enabled };
  }, [status]);

  const enabledPct = counts.total > 0 ? Math.round((counts.enabled / counts.total) * 100) : 0;

  return (
    <div className="space-y-5">
      <div>
        <p className="eyebrow">Command Center</p>
        <h1 className="mt-1 text-2xl font-bold uppercase tracking-tight">Overview</h1>
        <p className="techmeta mt-1.5 normal-case">
          Operational summary for{" "}
          <code className="text-foreground/80">{configFile}</code>
        </p>
      </div>

      {status.state === "loading" && (
        <>
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Connecting…
          </p>
          <LoadingSkeleton />
        </>
      )}
      {status.state === "error" && (
        <ErrorState message={status.message} onRetry={() => setReloadKey((k) => k + 1)} />
      )}

      {status.state === "ok" && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatusTile label="Pipeline Status" value="OPERATIONAL" footer="All systems nominal" />
            <Tile label="Total Jobs" value={<CountUpValue value={counts.total} />} footer="Configured ETLs" />
            <Tile
              label="Enabled"
              value={<CountUpValue value={counts.enabled} />}
              footer={`${enabledPct}% of fleet`}
              badge={
                counts.enabled > 0 ? (
                  <span className="rounded-[3px] bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide text-emerald-600 ring-1 ring-inset ring-emerald-500/30">
                    active
                  </span>
                ) : undefined
              }
            />
            <Tile label="Disabled" value={<CountUpValue value={counts.disabled} />} footer="Paused pipelines" />
          </div>

          <Panel>
            <PanelHeader
              eyebrow="Signals"
              title="Issue overview"
              right="findings · statistics"
            />
            <PanelBody className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Signal label="Errors" value={signals.findings?.error} to="/findings" tone="error" />
              <Signal label="Warnings" value={signals.findings?.warning} to="/findings" tone="warning" />
              <Signal label="Row loss" value={signals.stats?.withRowLoss} to="/statistics" tone="warning" />
              <Signal label="PK issues" value={signals.stats?.withPkIssues} to="/statistics" tone="error" />
            </PanelBody>
          </Panel>

          <div className="grid gap-3 lg:grid-cols-3">
            {/* Configured-jobs roster — the "subject list" of the console. */}
            <Panel className="lg:col-span-2">
              <PanelHeader eyebrow="Pipeline" title="Configured jobs" right={`${counts.total} total`} />
              <ul className="divide-y divide-border">
                {status.jobs.map((j) => (
                  <li
                    key={j.config_key}
                    className="flex items-center justify-between gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-accent"
                  >
                    <span className="flex min-w-0 items-center gap-2.5">
                      <StatusDot status={j.enabled ? "healthy" : "idle"} />
                      <span className="min-w-0 truncate">
                        <span className="font-mono text-foreground">{j.config_key}</span>{" "}
                        <span className="text-muted-foreground">— {j.pipeline_name}</span>
                      </span>
                    </span>
                    <span
                      className={
                        j.enabled
                          ? "shrink-0 rounded-[3px] bg-primary/15 px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.08em] text-primary ring-1 ring-inset ring-primary/30"
                          : "shrink-0 rounded-[3px] bg-muted px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground ring-1 ring-inset ring-border"
                      }
                    >
                      {j.enabled ? "enabled" : "disabled"}
                    </span>
                  </li>
                ))}
              </ul>
            </Panel>

            <div className="space-y-3">
              <Panel accent="healthy">
                <PanelHeader eyebrow="Backend" title="Connection status" right="FastAPI" />
                <PanelBody>
                  <p className="flex items-start gap-2 text-sm">
                    <StatusDot status="healthy" pulse className="mt-1" />
                    <span>
                      <span className="font-medium text-primary">Connected.</span>{" "}
                      <span className="text-muted-foreground">
                        {counts.total} job{counts.total === 1 ? "" : "s"} ({counts.enabled} enabled).
                      </span>
                    </span>
                  </p>
                </PanelBody>
              </Panel>

              <Panel>
                <PanelHeader eyebrow="Fleet" title="Enabled ratio" right={`${enabledPct}%`} />
                <PanelBody className="space-y-2">
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary shadow-[0_0_10px] shadow-primary/50 transition-[width] duration-500"
                      style={{ width: `${enabledPct}%` }}
                    />
                  </div>
                  <div className="flex justify-between techmeta normal-case">
                    <span>{counts.enabled} enabled</span>
                    <span>{counts.disabled} disabled</span>
                  </div>
                </PanelBody>
              </Panel>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
