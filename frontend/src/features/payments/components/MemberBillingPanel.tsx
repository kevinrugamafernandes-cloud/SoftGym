import { useState } from "react";
import { Link } from "react-router-dom";
import { CreditCard } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePermissions } from "@/features/auth";
import { useGymCurrency, usePayments } from "@/hooks/usePayments";
import { cn, formatDate } from "@/utils";
import type { Member, Payment } from "@/types";

import { PaymentFormDialog } from "./PaymentFormDialog";
import { PaymentsTable } from "./PaymentsTable";
import { VoidPaymentDialog } from "./VoidPaymentDialog";

const TONE = {
  vigente: "border-success/30 bg-success/10 text-success",
  por_vencer: "border-warning/40 bg-warning/10 text-warning",
  vencida: "border-destructive/40 bg-destructive/10 text-destructive",
} as const;

/** Membresía vigente, botón de cobro/renovación y últimos pagos del socio. */
export function MemberBillingPanel({ member }: { member: Member }) {
  const { can } = usePermissions();
  const currency = useGymCurrency();
  const payments = usePayments({
    date_from: "", date_to: "", method: "", member_id: member.id, include_voided: true, page: 1, size: 5,
  });
  const [charging, setCharging] = useState(false);
  const [voidTarget, setVoidTarget] = useState<Payment | null>(null);
  const ms = member.membership;
  const total = payments.data?.total ?? 0;

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0 pb-3">
        <CardTitle className="text-base">Membresía y pagos</CardTitle>
        {can("payments.create") && (
          <Button variant="gold" size="sm" onClick={() => setCharging(true)}>
            <CreditCard className="mr-2 h-4 w-4" aria-hidden />
            {ms ? "Renovar / cobrar" : "Cobrar membresía"}
          </Button>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {ms ? (
          <div className={cn("flex flex-col gap-1 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between", TONE[ms.state])}>
            <div>
              <p className="text-sm font-semibold">{ms.label}</p>
              <p className="text-xs text-muted-foreground">
                {ms.plan_name} · del {formatDate(ms.start_date)} al {formatDate(ms.end_date)}
              </p>
            </div>
            {ms.days_remaining >= 0 && (
              <p className="text-2xl font-bold tabular-nums">
                {ms.days_remaining}<span className="ml-1 text-xs font-normal text-muted-foreground">{ms.days_remaining === 1 ? "día" : "días"}</span>
              </p>
            )}
          </div>
        ) : (
          <p className="rounded-lg border border-border bg-input/30 p-3 text-sm text-muted-foreground">
            Este socio aún no tiene membresías pagadas.
          </p>
        )}

        <PaymentsTable
          payments={payments.data?.items}
          currency={currency}
          loading={payments.isLoading}
          error={payments.error}
          onRetry={() => void payments.refetch()}
          canVoid={can("payments.void")}
          onVoid={setVoidTarget}
          hideMember
          emptyTitle="Sin pagos registrados"
          emptyDescription="Los cobros de este socio aparecerán aquí."
        />
        {total > 5 && (
          <p className="text-right text-xs text-muted-foreground">
            Mostrando los 5 más recientes de {total}.{" "}
            <Link to={`/payments?desde=&hasta=&socio=${member.id}`} className="text-gold hover:underline">Ver historial de pagos</Link>
          </p>
        )}
      </CardContent>

      {charging && (
        <PaymentFormDialog open member={member} currency={currency} onOpenChange={(o) => !o && setCharging(false)} />
      )}
      <VoidPaymentDialog payment={voidTarget} currency={currency} onOpenChange={(o) => !o && setVoidTarget(null)} />
    </Card>
  );
}
