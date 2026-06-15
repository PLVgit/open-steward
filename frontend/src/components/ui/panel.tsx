import * as React from "react";

import { cn } from "@/lib/utils";

type Accent = "none" | "primary" | "healthy" | "warning" | "error" | "info";

const ACCENT_LINE: Record<Accent, string> = {
  none: "",
  primary: "before:bg-primary",
  healthy: "before:bg-emerald-400",
  warning: "before:bg-amber-400",
  error: "before:bg-destructive",
  info: "before:bg-sky-400",
};

interface PanelProps extends React.HTMLAttributes<HTMLDivElement> {
  accent?: Accent;
}

/** A framed instrument panel — the primary content surface. Sharp corners,
 *  crisp neutral border, optional neon accent rail along the top edge. */
const Panel = React.forwardRef<HTMLDivElement, PanelProps>(
  ({ className, accent = "none", ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "relative overflow-hidden rounded-sm border border-border bg-card shadow-[0_1px_0_0_hsl(0_0%_100%/0.03)_inset,0_10px_30px_-18px_rgb(0_0_0/0.9)]",
        accent !== "none" &&
          "before:absolute before:inset-x-0 before:top-0 before:z-10 before:h-[2px] before:content-['']",
        ACCENT_LINE[accent],
        className,
      )}
      {...props}
    />
  ),
);
Panel.displayName = "Panel";

interface PanelHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, "title"> {
  eyebrow?: React.ReactNode;
  title?: React.ReactNode;
  right?: React.ReactNode;
}

/** The header strip of a Panel — slightly lifted, divided from the body. */
function PanelHeader({ eyebrow, title, right, className, children, ...props }: PanelHeaderProps) {
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 border-b border-border bg-white/[0.015] px-4 py-2.5",
        className,
      )}
      {...props}
    >
      {children ?? (
        <>
          <div className="min-w-0">
            {eyebrow && <div className="eyebrow">{eyebrow}</div>}
            {title && (
              <div className="truncate text-sm font-semibold tracking-tight text-foreground">
                {title}
              </div>
            )}
          </div>
          {right && <div className="techmeta shrink-0 normal-case">{right}</div>}
        </>
      )}
    </div>
  );
}

function PanelBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4", className)} {...props} />;
}

export { Panel, PanelHeader, PanelBody };
