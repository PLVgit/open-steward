import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { Panel, PanelBody, PanelHeader } from "@/components/ui/panel";
import { StatusDot } from "@/components/ui/status-dot";
import { api, ApiError } from "@/lib/api";
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
    <div className="relative overflow-hidden rounded-sm border border-white/10 bg-white px-4 py-3.5 text-zinc-950 shadow-[0_10px_30px_-18px_rgb(0_0_0/0.9)]">
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

/** The single neon-green "headline status" tile (echoes the OPTIMAL card). */
function StatusTile({ label, value, footer }: { label: string; value: string; footer: string }) {
  return (
    <div className="relative overflow-hidden rounded-sm border border-primary/60 bg-primary/10 px-4 py-3.5 shadow-[0_0_34px_-12px_hsl(142_84%_52%/0.6)]">
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

export function OverviewPage() {
  const { configFile } = useConfig();
  const [status, setStatus] = useState<Status>({ state: "loading" });

  useEffect(() => {
    let cancelled = false;
    setStatus({ state: "loading" });
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
    return () => {
      cancelled = true;
    };
  }, [configFile]);

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
        <Panel>
          <PanelBody className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Connecting…
          </PanelBody>
        </Panel>
      )}
      {status.state === "error" && (
        <Panel accent="error">
          <PanelBody className="flex items-center gap-2 text-sm text-destructive" role="alert">
            <AlertTriangle className="h-4 w-4 shrink-0" /> {status.message}
          </PanelBody>
        </Panel>
      )}

      {status.state === "ok" && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatusTile label="Pipeline Status" value="OPERATIONAL" footer="All systems nominal" />
            <Tile label="Total Jobs" value={counts.total} footer="Configured ETLs" />
            <Tile
              label="Enabled"
              value={counts.enabled}
              footer={`${enabledPct}% of fleet`}
              badge={
                counts.enabled > 0 ? (
                  <span className="rounded-[3px] bg-emerald-500/15 px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-wide text-emerald-600 ring-1 ring-inset ring-emerald-500/30">
                    active
                  </span>
                ) : undefined
              }
            />
            <Tile label="Disabled" value={counts.disabled} footer="Paused pipelines" />
          </div>

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
                      className="h-full rounded-full bg-primary shadow-[0_0_10px] shadow-primary/50"
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
