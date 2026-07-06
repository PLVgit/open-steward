import { AlertTriangle, RotateCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Panel, PanelBody } from "@/components/ui/panel";

/** Consistent error panel with a retry action — no dead ends. */
export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <Panel accent="error">
      <PanelBody className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm text-destructive" role="alert">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {message}
        </p>
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RotateCw className="h-3.5 w-3.5" /> Retry
        </Button>
      </PanelBody>
    </Panel>
  );
}
