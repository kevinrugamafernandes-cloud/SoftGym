import { CalendarClock } from "lucide-react";
import { formatDate } from "@/utils";
import { cn } from "@/utils";
import type { MembershipSummary } from "@/types";

const TONE: Record<MembershipSummary["state"], string> = {
  vigente: "text-success",
  por_vencer: "text-warning",
  vencida: "text-destructive",
};

/** "Plan Mensual · Vence en 3 días (hasta 19 oct 2026)" con el color del estado. */
export function MembershipStateText({
  membership, className,
}: { membership: MembershipSummary | null | undefined; className?: string }) {
  if (!membership) {
    return <p className={cn("text-xs text-muted-foreground", className)}>Sin membresías previas.</p>;
  }
  return (
    <p className={cn("flex items-center gap-1.5 text-xs", className)}>
      <CalendarClock className={cn("h-3.5 w-3.5 shrink-0", TONE[membership.state])} aria-hidden />
      <span className="text-muted-foreground">{membership.plan_name} ·</span>
      <span className={cn("font-medium", TONE[membership.state])}>{membership.label}</span>
      <span className="text-muted-foreground">(hasta {formatDate(membership.end_date)})</span>
    </p>
  );
}
