import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

// Sharp rectangular status chips, like the REC / CALIB / STBY tags on an
// industrial monitoring console. Uppercase, tight, mono-friendly.
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-[3px] px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase leading-none tracking-[0.08em] ring-1 ring-inset",
  {
    variants: {
      variant: {
        error: "bg-destructive/15 text-destructive ring-destructive/40",
        warning: "bg-amber-400/15 text-amber-300 ring-amber-400/40",
        info: "bg-sky-400/15 text-sky-300 ring-sky-400/40",
        success: "bg-primary/15 text-primary ring-primary/40",
        muted: "bg-muted text-muted-foreground ring-border",
        solid: "bg-primary text-primary-foreground ring-primary",
      },
    },
    defaultVariants: {
      variant: "muted",
    },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
