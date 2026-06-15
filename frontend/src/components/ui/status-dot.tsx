import { cn } from "@/lib/utils";

export type Status = "healthy" | "warning" | "error" | "info" | "idle";

const COLOR: Record<Status, string> = {
  healthy: "bg-emerald-400",
  warning: "bg-amber-400",
  error: "bg-destructive",
  info: "bg-sky-400",
  idle: "bg-slate-500",
};

/** A small semantic status indicator; `pulse` adds a soft ping (for live/healthy). */
export function StatusDot({
  status,
  pulse = false,
  className,
}: {
  status: Status;
  pulse?: boolean;
  className?: string;
}) {
  return (
    <span className={cn("relative inline-flex h-2 w-2", className)}>
      {pulse && (
        <span
          className={cn(
            "absolute inline-flex h-full w-full animate-ping rounded-full opacity-60",
            COLOR[status],
          )}
        />
      )}
      <span className={cn("relative inline-flex h-2 w-2 rounded-full", COLOR[status])} />
    </span>
  );
}
