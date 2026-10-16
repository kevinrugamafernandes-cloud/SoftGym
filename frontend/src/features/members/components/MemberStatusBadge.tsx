import { Badge, type BadgeProps } from "@/components/ui/badge";
import { MEMBER_STATUS_LABELS } from "@/lib/labels";
import { cn } from "@/utils";
import type { MemberStatus } from "@/types";

const VARIANT: Record<MemberStatus, BadgeProps["variant"]> = {
  activo: "success",
  por_vencer: "warning",
  moroso: "destructive",
  inactivo: "outline",
};

export function MemberStatusBadge({ status, className }: { status: MemberStatus; className?: string }) {
  return (
    <Badge variant={VARIANT[status]} className={cn(status === "inactivo" && "text-muted-foreground", className)}>
      {MEMBER_STATUS_LABELS[status]}
    </Badge>
  );
}
