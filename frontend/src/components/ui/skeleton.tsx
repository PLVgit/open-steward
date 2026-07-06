import { cn } from "@/lib/utils";

/** A pulsing placeholder block, shaped like the content it stands in for. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("animate-pulse rounded-sm bg-muted/70", className)} />;
}
