import { NavLink, Outlet } from "react-router-dom";
import {
  Activity,
  BarChart3,
  FileSearch,
  GitBranch,
  LayoutDashboard,
  Workflow,
} from "lucide-react";

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

export function AppShell() {
  const { configFile, setConfigFile } = useConfig();

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
            <label className="flex items-center overflow-hidden rounded-sm border border-input bg-background focus-within:border-primary focus-within:ring-1 focus-within:ring-primary/40">
              <span className="eyebrow border-r border-border bg-card px-2.5 py-2">Config</span>
              <input
                aria-label="Config file"
                value={configFile}
                onChange={(e) => setConfigFile(e.target.value)}
                className="h-9 w-60 bg-transparent px-3 font-mono text-xs text-foreground outline-none"
              />
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
