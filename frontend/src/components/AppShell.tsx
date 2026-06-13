import { NavLink, Outlet } from "react-router-dom";
import { Activity, BarChart3, FileSearch, GitBranch, LayoutDashboard } from "lucide-react";

import { cn } from "@/lib/utils";
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
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="w-60 shrink-0 border-r bg-card p-4">
        <div className="mb-6 px-2">
          <h1 className="text-lg font-semibold">Open Steward</h1>
          <p className="text-xs text-muted-foreground">Pipeline intelligence</p>
        </div>
        <nav className="space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b bg-card px-6 py-3">
          <span className="text-sm text-muted-foreground">
            Local-first virtual data steward
          </span>
          <label className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">Config</span>
            <input
              aria-label="Config file"
              value={configFile}
              onChange={(e) => setConfigFile(e.target.value)}
              className="h-8 w-56 rounded-md border border-input bg-background px-2 font-mono text-xs"
            />
          </label>
        </header>
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
