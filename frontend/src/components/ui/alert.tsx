import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/utils";

const alertVariants = cva("relative flex gap-3 rounded-lg border p-3 text-sm", {
  variants: {
    variant: {
      info: "border-gold/30 bg-gold/5 text-foreground [&>svg]:text-gold",
      success: "border-success/30 bg-success/10 text-foreground [&>svg]:text-success",
      warning: "border-warning/40 bg-warning/10 text-foreground [&>svg]:text-warning",
      destructive: "border-destructive/40 bg-destructive/10 text-foreground [&>svg]:text-destructive",
    },
  },
  defaultVariants: { variant: "info" },
});

export interface AlertProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof alertVariants> {
  icon?: React.ReactNode;
}

/** Aviso en línea. `destructive`/`warning` usan role="alert"; el resto, role="status". */
function Alert({ className, variant, icon, children, ...props }: AlertProps) {
  const urgent = variant === "destructive" || variant === "warning";
  return (
    <div role={urgent ? "alert" : "status"} className={cn(alertVariants({ variant }), className)} {...props}>
      {icon}
      <div className="min-w-0 flex-1 space-y-1">{children}</div>
    </div>
  );
}

function AlertTitle({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn("font-medium leading-tight", className)} {...props} />;
}

function AlertDescription({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("text-[13px] leading-snug text-muted-foreground", className)} {...props} />;
}

export { Alert, AlertTitle, AlertDescription };
