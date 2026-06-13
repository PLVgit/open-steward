import { useEffect, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api, ApiError } from "@/lib/api";
import { useConfig } from "@/context/ConfigContext";
import type { PipelineJob } from "@/lib/types";

type Status =
  | { state: "loading" }
  | { state: "ok"; jobs: PipelineJob[] }
  | { state: "error"; message: string };

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

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Backend connection</CardTitle>
          <CardDescription>
            Reading config <code className="font-mono">{configFile}</code> via the API.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {status.state === "loading" && (
            <p className="text-sm text-muted-foreground">Connecting…</p>
          )}
          {status.state === "error" && (
            <p className="text-sm text-destructive" role="alert">
              {status.message}
            </p>
          )}
          {status.state === "ok" && (
            <div className="space-y-1">
              <p className="text-sm">
                <span className="font-medium text-green-500">Connected.</span>{" "}
                {status.jobs.length} job{status.jobs.length === 1 ? "" : "s"} (
                {status.jobs.filter((j) => j.enabled).length} enabled).
              </p>
              <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                {status.jobs.map((j) => (
                  <li key={j.config_key} className="font-mono">
                    {j.config_key} — {j.pipeline_name}
                    {!j.enabled && " (disabled)"}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
