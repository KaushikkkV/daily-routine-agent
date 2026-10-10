import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-zinc-800 text-zinc-100 hover:bg-zinc-700",
        secondary:
          "border-transparent bg-zinc-700/60 text-zinc-300 hover:bg-zinc-700",
        destructive:
          "border-transparent bg-rose-900/60 text-rose-200 border-rose-700/50",
        outline: "text-zinc-300 border-zinc-700",
        deepWork:
          "border-indigo-500/30 bg-indigo-500/15 text-indigo-300 shadow-sm shadow-indigo-500/10",
        buffer:
          "border-emerald-500/30 bg-emerald-500/15 text-emerald-300 shadow-sm shadow-emerald-500/10",
        shallow:
          "border-amber-500/30 bg-amber-500/15 text-amber-300 shadow-sm shadow-amber-500/10",
        health:
          "border-cyan-500/30 bg-cyan-500/15 text-cyan-300 shadow-sm shadow-cyan-500/10",
        critical:
          "border-red-500/40 bg-red-500/20 text-red-300 animate-pulse",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export { Badge, badgeVariants };
