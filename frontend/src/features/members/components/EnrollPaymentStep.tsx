import { useEffect, useState } from "react";
import { AlertCircle, ArrowLeft, CalendarRange, UserRound } from "lucide-react";

import { DialogFooter } from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { usePermissions } from "@/features/auth";
import { NoCashSessionAlert } from "@/features/cash/components/CashSessionIndicator";
import { PAYMENT_METHODS, previewPeriod } from "@/features/payments/schemas";
import { useEnroll } from "@/hooks/useAdmin";
import { useCurrentCashSession } from "@/hooks/useCashSessions";
import { useCreateMember } from "@/hooks/useMembers";
import { usePlans } from "@/hooks/usePlans";
import { toast } from "@/hooks/useToast";
import { getErrorCode } from "@/lib/axios";
import { todayISO } from "@/lib/dates";
import { PAYMENT_METHOD_LABELS, REFERENCE_REQUIRED_METHODS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import { isDecimal, normalizeDecimal, trimDecimal } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn, formatDate } from "@/utils";
import type { EnrollmentResult, Member, MemberCreatePayload, PaymentMethod } from "@/types";

interface Props {
  member: MemberCreatePayload;
  currency: string;
  onBack: (error?: { code?: string; message: string }) => void;
  onEnrolled: (result: EnrollmentResult) => void;
  /** Alta sin cobro (solo administradores): el socio queda inactivo. */
  onCreatedWithoutPayment: (member: Member) => void;
}

/**
 * Paso 2 de la inscripción: plan y cobro. El socio y su primer pago se registran JUNTOS
 * (POST /members/enroll): si el cobro falla, el socio no queda creado.
 */
export function EnrollPaymentStep({ member, currency, onBack, onEnrolled, onCreatedWithoutPayment }: Props) {
  const { can } = usePermissions();
  const plans = usePlans(true);
  const cash = useCurrentCashSession();
  const enroll = useEnroll();
  const createMember = useCreateMember();

  const [planId, setPlanId] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<PaymentMethod>("efectivo");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<string | null>(null);
  const plan = plans.data?.find((p) => p.id === planId);

  // Preselecciona la mensualidad (el plan más común) y toma su precio.
  useEffect(() => {
    if (!planId && plans.data?.length) {
      const monthly = plans.data.find((p) => p.duration_days === 30) ?? plans.data[0];
      setPlanId(monthly.id);
    }
  }, [plans.data, planId]);
  useEffect(() => { if (plan) setAmount(trimDecimal(plan.price)); }, [plan]);

  const amountOk = isDecimal(amount);
  const amountNumber = amountOk ? Number(normalizeDecimal(amount)) : null;
  const discount = plan && amountNumber !== null && amountNumber < Number(plan.price) ? Number(plan.price) - amountNumber : 0;
  const period = plan ? previewPeriod(null, todayISO(), plan.duration_days) : null;
  const needsRef = REFERENCE_REQUIRED_METHODS.has(method);
  const noCash = cash.isSuccess && cash.data === null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setError(null);
    if (!plan) return setError("Seleccione el plan.");
    if (!amountOk) return setError("Monto inválido (use números, con hasta 2 decimales).");
    if (needsRef && !reference.trim()) return setError(`Para ${PAYMENT_METHOD_LABELS[method]} indique el número de referencia.`);
    try {
      const result = await enroll.mutateAsync({
        member,
        payment: { plan_id: plan.id, amount: normalizeDecimal(amount), method, reference: reference.trim() || null },
      });
      toast({
        variant: "success",
        title: `${result.member.full_name} inscrito`,
        description: `${plan.name} · ${formatMoney(result.payment.amount, currency)} · ${result.payment.receipt_code}`,
      });
      onEnrolled(result);
    } catch (err) {
      const code = getErrorCode(err);
      const message = reportError(err, "No se pudo inscribir al socio");
      if (code === "member_exists" || code === "member_deleted" || code === "validation_error") {
        onBack({ code, message });     // el problema está en los datos del socio
        return;
      }
      if (code === "cash_session_required") void cash.refetch();
      setError(message);
    }
  };

  const saveWithoutPayment = async () => {
    setError(null);
    try {
      const created = await createMember.mutateAsync(member);
      toast({ title: "Socio registrado SIN cobro", description: `${created.full_name} queda inactivo hasta su primer pago.` });
      onCreatedWithoutPayment(created);
    } catch (err) {
      const code = getErrorCode(err);
      const message = reportError(err, "No se pudo registrar el socio");
      if (code === "member_exists" || code === "member_deleted") onBack({ code, message });
      else setError(message);
    }
  };

  const busy = enroll.isPending || createMember.isPending;

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div className="flex items-center gap-3 rounded-lg border border-border bg-input/30 p-3">
        <UserRound className="h-5 w-5 shrink-0 text-gold" aria-hidden />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">{member.first_name} {member.last_name}</p>
          <p className="text-xs tabular-nums text-muted-foreground">Cédula {member.identification}{member.phone ? ` · ${member.phone}` : ""}</p>
        </div>
      </div>

      {noCash && <NoCashSessionAlert />}
      {error && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{error}</AlertDescription>
        </Alert>
      )}

      <fieldset className="space-y-2">
        <legend className="mb-1 text-sm font-medium">Plan</legend>
        {plans.isLoading ? <p className="text-sm text-muted-foreground">Cargando planes…</p> : (
          <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="Plan">
            {plans.data?.map((p) => (
              <button key={p.id} type="button" role="radio" aria-checked={p.id === planId} onClick={() => setPlanId(p.id)}
                className={cn(
                  "rounded-lg border p-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  p.id === planId ? "border-gold bg-gold/10" : "border-border bg-input/30 hover:border-gold/40"
                )}>
                <p className="text-sm font-medium text-foreground">{p.name}</p>
                <p className="text-xs text-muted-foreground">{p.duration_days} {p.duration_days === 1 ? "día" : "días"}</p>
                <p className="mt-1 font-semibold tabular-nums text-gold">{formatMoney(p.price, currency)}</p>
              </button>
            ))}
          </div>
        )}
        {plans.data?.length === 0 && <p className="text-sm text-warning">No hay planes activos: un administrador debe activarlos en Configuración.</p>}
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="enroll-amount">Monto ({currency})</Label>
          <Input id="enroll-amount" inputMode="decimal" autoComplete="off" value={amount} className="tabular-nums"
            onChange={(e) => setAmount(e.target.value)} />
          {discount > 0 && <p className="text-xs text-warning">Descuento de {formatMoney(discount, currency)}</p>}
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="enroll-method">Método de pago</Label>
          <Select id="enroll-method" value={method} onChange={(e) => setMethod(e.target.value as PaymentMethod)}>
            {PAYMENT_METHODS.map((x) => <option key={x} value={x}>{PAYMENT_METHOD_LABELS[x]}</option>)}
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="enroll-ref">Referencia {needsRef ? <span className="text-destructive">*</span> : <span className="text-muted-foreground">(opcional)</span>}</Label>
          <Input id="enroll-ref" autoComplete="off" maxLength={100} value={reference} onChange={(e) => setReference(e.target.value)} />
        </div>
      </div>

      {plan && period && (
        <p className="flex items-center gap-2 rounded-lg border border-gold/30 bg-gold/5 p-3 text-sm">
          <CalendarRange className="h-4 w-4 shrink-0 text-gold" aria-hidden />
          Membresía del <strong>{formatDate(period.start)}</strong> al <strong>{formatDate(period.end)}</strong>
        </p>
      )}

      <DialogFooter className="sm:justify-between">
        <Button type="button" variant="ghost" onClick={() => onBack()} disabled={busy}>
          <ArrowLeft className="mr-2 h-4 w-4" aria-hidden /> Datos del socio
        </Button>
        <div className="flex flex-col-reverse gap-2 sm:flex-row">
          {can("members.create_without_payment") && (
            <Button type="button" variant="outline" onClick={() => void saveWithoutPayment()} disabled={busy}
              title="El socio queda inactivo hasta que pague">
              Registrar sin cobro
            </Button>
          )}
          <Button type="submit" variant="gold" loading={enroll.isPending} disabled={busy || !plan}>
            Inscribir y cobrar {amountNumber !== null ? formatMoney(amountNumber, currency) : ""}
          </Button>
        </div>
      </DialogFooter>
    </form>
  );
}
