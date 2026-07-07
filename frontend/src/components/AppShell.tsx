import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  BarChart3,
  FileSearch,
  GitBranch,
  LayoutDashboard,
  Workflow,
} from "lucide-react";

import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { StatusDot } from "@/components/ui/status-dot";
import { useConfig } from "@/context/ConfigContext";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/graph", label: "Graph", icon: GitBranch, end: false },
  { to: "/findings", label: "Findings", icon: Activity, end: false },
  { to: "/statistics", label: "Statistics", icon: BarChart3, end: false },
  { to: "/profile", label: "Profile", icon: FileSearch, end: false },
];

// Bundled sample configs — the offline fallback when /configs/ is unreachable.
const KNOWN_CONFIGS = ["demo_config.csv", "showcase_config.csv", "sample_config.csv"];

export function AppShell() {
  const { configFile, setConfigFile, recentConfigs } = useConfig();
  // Draft-then-commit: the config only applies on Enter/blur, so pages don't
  // refetch (and flash 404 errors) on every keystroke while a filename is typed.
  const [draft, setDraft] = useState(configFile);
  const [justApplied, setJustApplied] = useState(false);
  // Configs actually available on the server (respects OPEN_STEWARD_CONFIG_DIR).
  const [serverConfigs, setServerConfigs] = useState<string[]>([]);

  useEffect(() => setDraft(configFile), [configFile]);

  useEffect(() => {
    api
      .listConfigs()
      .then((c) => {
        if (Array.isArray(c?.files)) setServerConfigs(c.files);
      })
      .catch(() => {
        /* suggestions fall back to recents + bundled names */
      });
  }, []);

  const commitDraft = () => {
    const next = draft.trim();
    if (next && next !== configFile) {
      setConfigFile(next);
      setJustApplied(true);
      window.setTimeout(() => setJustApplied(false), 1400);
    } else {
      setDraft(configFile); // revert an empty or unchanged draft
    }
  };

  const suggestions = Array.from(
    new Set([...recentConfigs, ...serverConfigs, ...KNOWN_CONFIGS]),
  );

  return (
    <div className="flex min-h-screen text-foreground">
      {/* ── Command sidebar ─────────────────────────────────────────────── */}
      <aside className="flex w-64 shrink-0 flex-col border-r border-border bg-card">
        {/* Brand block */}
        <div className="flex items-center gap-3 border-b border-border px-5 py-4">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-sm border border-border bg-background text-primary">
            <Workflow className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-bold uppercase tracking-[0.16em] text-foreground">
              Open Steward
            </h1>
            <p className="techmeta mt-0.5">SYS · STEWARD.CORE</p>
          </div>
        </div>

        {/* Primary navigation */}
        <div className="px-3 py-4">
          <div className="eyebrow px-2 pb-2">Console</div>
          <nav className="space-y-1">
            {NAV.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    "group flex items-center gap-3 rounded-sm border px-3 py-2 text-sm font-medium tracking-tight transition-colors",
                    isActive
                      ? "border-foreground/0 bg-foreground text-background"
                      : "border-transparent text-muted-foreground hover:border-border hover:bg-accent hover:text-foreground",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={cn("h-4 w-4 shrink-0", !isActive && "text-muted-foreground")} />
                    <span className="truncate">{label}</span>
                    {isActive && (
                      <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_8px] shadow-primary/70" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Lower system section */}
        <div className="mt-auto space-y-3 px-3 pb-3">
          <div className="rounded-sm border border-border bg-background/60 px-3 py-2.5">
            <div className="eyebrow pb-1.5">System</div>
            <div className="flex items-center justify-between text-xs">
              <span className="flex items-center gap-2 text-muted-foreground">
                <StatusDot status="healthy" pulse />
                <span className="font-medium text-foreground">Engine online</span>
              </span>
              <span className="techmeta normal-case">v0.1</span>
            </div>
            <div className="techmeta mt-2 truncate">RECONCILE :: READY</div>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* ── System top bar ────────────────────────────────────────────── */}
        <header className="glass-panel sticky top-0 z-20 flex items-center justify-between gap-4 border-x-0 border-t-0 px-6 py-3">
          <div className="flex items-center gap-4">
            <span className="inline-flex items-center gap-1.5 rounded-[3px] bg-primary px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.12em] text-primary-foreground">
              <span className="h-1.5 w-1.5 rounded-full bg-primary-foreground" />
              System Active
            </span>
            <span className="hidden font-semibold uppercase tracking-[0.18em] text-foreground sm:inline">
              Pipeline Monitoring
            </span>
            <span className="techmeta hidden md:inline">ENGINE :: RECONCILE</span>
          </div>

          <div className="flex items-center gap-3">
            <span className="techmeta hidden lg:inline">Scope</span>
            <label
              className={cn(
                "flex items-center overflow-hidden rounded-sm border bg-background transition-colors focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/40",
                justApplied ? "border-primary ring-1 ring-primary/40" : "border-input",
              )}
            >
              <span className="eyebrow border-r border-border bg-card px-2.5 py-2">Config</span>
              <input
                aria-label="Config file"
                list="config-suggestions"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={commitDraft}
                onKeyDown={(e) => {
                  if (e.key === "Enter") commitDraft();
                  else if (e.key === "Escape") setDraft(configFile);
                }}
                className="h-9 w-60 bg-transparent px-3 font-mono text-xs text-foreground outline-none"
              />
              {justApplied && (
                <span className="pr-2.5 font-mono text-[10px] font-bold uppercase tracking-wide text-primary">
                  ✓
                </span>
              )}
              <datalist id="config-suggestions">
                {suggestions.map((s) => (
                  <option key={s} value={s} />
                ))}
              </datalist>
            </label>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
