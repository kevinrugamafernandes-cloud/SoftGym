import { useEffect, useRef, useState } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, AlertTriangle, CalendarRange } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { NoCashSessionAlert } from "@/features/cash/components/CashSessionIndicator";
import { useCurrentCashSession } from "@/hooks/useCashSessions";
import { useCreatePayment } from "@/hooks/usePayments";
import { usePlans } from "@/hooks/usePlans";
import { toast } from "@/hooks/useToast";
import { getErrorCode, getFieldErrors } from "@/lib/axios";
import { todayISO } from "@/lib/dates";
import { describeInvalidFields } from "@/lib/form-errors";
import { PAYMENT_METHOD_LABELS, REFERENCE_REQUIRED_METHODS } from "@/lib/labels";
import { formatMoney } from "@/lib/money";
import { normalizeDecimal, isDecimal, trimDecimal } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn, formatDate } from "@/utils";
import type { Member, Payment } from "@/types";

import {
  PAYMENT_FORM_FIELDS, PAYMENT_METHODS, emptyPaymentForm, paymentFormSchema, previewPeriod,
  toPaymentPayload, type PaymentFormValues,
} from "../schemas";
import { MemberPicker } from "./MemberPicker";
import { ReceiptSummary } from "./ReceiptSummary";

interface PaymentFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Socio preseleccionado (p. ej. desde su ficha). */
  member?: Member;
  /** Moneda del gimnasio para mostrar montos (la de la caja). */
  currency?: string;
}

export function PaymentFormDialog({ open, onOpenChange, member, currency = "CRC" }: PaymentFormDialogProps) {
  const [created, setCreated] = useState<Payment | null>(null);
  const [createdPhone, setCreatedPhone] = useState<string | null>(null);
  const [formKey, setFormKey] = useState(0);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        {created ? (
          <>
            <DialogHeader>
              <DialogTitle>Cobro registrado</DialogTitle>
              <DialogDescription>El comprobante quedó guardado y la membresía del socio se actualizó.</DialogDescription>
            </DialogHeader>
            <ReceiptSummary payment={created} currency={currency} memberPhone={createdPhone} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
              {!member && (
                <Button type="button" variant="gold" onClick={() => { setCreated(null); setFormKey((k) => k + 1); }}>
                  Nuevo cobro
                </Button>
              )}
            </DialogFooter>
          </>
        ) : (
          <>
            <DialogHeader>
              <DialogTitle>Registrar cobro</DialogTitle>
              <DialogDescription>
                {member ? `Cobro de membresía para ${member.full_name}.` : "Busque al socio, elija el plan y el método de pago."}
              </DialogDescription>
            </DialogHeader>
            {/* Se monta al abrir: el formulario siempre empieza limpio. */}
            <PaymentForm key={formKey} member={member} currency={currency} onClose={() => onOpenChange(false)} onCreated={(p, phone) => { setCreated(p); setCreatedPhone(phone); }} />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-xs text-destructive">{message}</p> : null;
}

const invalid = (hasError: unknown) => (hasError ? "border-destructive focus-visible:ring-destructive" : undefined);

interface PaymentFormProps {
  member?: Member;
  currency: string;
  onClose: () => void;
  onCreated: (payment: Payment, memberPhone: string | null) => void;
}

function PaymentForm({ member, currency, onClose, onCreated }: PaymentFormProps) {
  const createPayment = useCreatePayment();
  const plans = usePlans(true);
  const cash = useCurrentCashSession();
  const noCashSession = cash.isSuccess && cash.data === null;

  const {
    register, handleSubmit, setValue, setError, clearErrors, watch, getValues,
    formState: { errors, isSubmitting },
  } = useForm<PaymentFormValues>({
    resolver: zodResolver(paymentFormSchema),
    defaultValues: emptyPaymentForm(member?.id),
  });

  const [selected, setSelected] = useState<Member | null>(member ?? null);
  const [formError, setFormError] = useState<string | null>(null);
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const amountTouched = useRef(false);

  const planId = watch("plan_id");
  const method = watch("method");
  const amount = watch("amount");
  const paymentDate = watch("payment_date");
  const plan = plans.data?.find((p) => p.id === planId);

  // Al elegir (o CAMBIAR) de plan, el monto vuelve a su precio de lista: un descuento escrito
  // para otro plan no debe arrastrarse sin que la recepcionista lo note.
  useEffect(() => {
    if (plan) {
      amountTouched.current = false;
      setValue("amount", trimDecimal(plan.price), { shouldValidate: getValues("amount") !== "" });
    }
  }, [plan?.id, setValue, getValues]); // eslint-disable-line react-hooks/exhaustive-deps

  // Cualquier cambio en los datos invalida la advertencia de duplicado anterior.
  useEffect(() => { setDuplicate(null); }, [planId, amount, selected?.id]);

  const amountNumber = isDecimal(amount ?? "") ? Number(normalizeDecimal(amount)) : null;
  const listPrice = plan ? Number(plan.price) : null;
  const discount = amountNumber !== null && listPrice !== null && amountNumber < listPrice ? listPrice - amountNumber : 0;
  const period = plan ? previewPeriod(selected?.membership, paymentDate, plan.duration_days) : null;
  const needsReference = REFERENCE_REQUIRED_METHODS.has(method);

  const submit = async (values: PaymentFormValues, confirmDuplicate: boolean) => {
    setFormError(null);
    try {
      const payment = await createPayment.mutateAsync(toPaymentPayload(values, confirmDuplicate));
      toast({
        variant: "success",
        title: `Cobro registrado · ${payment.receipt_code}`,
        description: `${payment.member.full_name}: ${formatMoney(payment.amount, currency)} (${PAYMENT_METHOD_LABELS[payment.method]}).`,
      });
      onCreated(payment, selected?.phone ?? null);
    } catch (err) {
      const code = getErrorCode(err);
      if (code === "possible_duplicate") {
        // No es un error del usuario: se pide confirmación explícita, sin Toast rojo.
        setDuplicate("Se acaba de registrar un pago idéntico para este socio (mismo plan y monto). ¿Es un cobro distinto?");
        return;
      }
      setFormError(reportError(err, "No se pudo registrar el cobro"));
      if (code === "cash_session_required") void cash.refetch();
      if (code === "reference_required") setError("reference", { type: "server", message: "Obligatorio para este método" });
      if (code === "payment_in_future") setError("payment_date", { type: "server", message: "La fecha no puede ser futura" });
      if (code === "plan_inactive") setError("plan_id", { type: "server", message: "El plan está inactivo" });
      for (const fe of getFieldErrors(err)) {
        if ((PAYMENT_FORM_FIELDS as readonly string[]).includes(fe.field)) {
          setError(fe.field as keyof PaymentFormValues, { type: "server", message: fe.message });
        }
      }
    }
  };

  const onSubmit = (values: PaymentFormValues) => submit(values, false);
  const onInvalid = (fields: FieldErrors<PaymentFormValues>) => setFormError(describeInvalidFields(fields));

  const confirmDuplicate = async () => {
    setConfirming(true);
    try {
      await handleSubmit((v) => submit(v, true), onInvalid)();
    } finally {
      setConfirming(false);
    }
  };

  const busy = isSubmitting || confirming;

  return (
    <form onSubmit={handleSubmit(onSubmit, onInvalid)} noValidate className="space-y-4">
      {noCashSession && <NoCashSessionAlert />}
      {formError && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{formError}</AlertDescription>
        </Alert>
      )}

      {/* ── Socio ── */}
      <div className="space-y-1.5">
        <Label htmlFor="member-picker">Socio</Label>
        <input type="hidden" {...register("member_id")} />
        <MemberPicker
          id="member-picker"
          value={selected}
          locked={Boolean(member)}
          autoFocus={!member}
          invalid={Boolean(errors.member_id)}
          onChange={(m) => {
            setSelected(m);
            setValue("member_id", m?.id ?? "", { shouldValidate: Boolean(m) });
            if (m) clearErrors("member_id");
          }}
        />
        <FieldError message={errors.member_id?.message} />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {/* ── Plan ── */}
        <div className="space-y-1.5">
          <Label htmlFor="plan_id">Plan</Label>
          <Select id="plan_id" aria-invalid={Boolean(errors.plan_id)} className={invalid(errors.plan_id)}
            disabled={plans.isLoading} {...register("plan_id")}>
            <option value="">{plans.isLoading ? "Cargando planes…" : "Seleccione un plan"}</option>
            {plans.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} · {p.duration_days} {p.duration_days === 1 ? "día" : "días"} · {formatMoney(p.price, currency)}
              </option>
            ))}
          </Select>
          {plans.data && plans.data.length === 0 && (
            <p className="text-xs text-warning">No hay planes activos. Un administrador debe crear o activar uno.</p>
          )}
          <FieldError message={errors.plan_id?.message} />
        </div>

        {/* ── Monto ── */}
        <div className="space-y-1.5">
          <Label htmlFor="amount">Monto cobrado ({currency})</Label>
          <Input id="amount" inputMode="decimal" autoComplete="off" placeholder="0"
            aria-invalid={Boolean(errors.amount)} className={cn("tabular-nums", invalid(errors.amount))}
            {...register("amount", { onChange: () => { amountTouched.current = true; } })} />
          {plan && discount > 0 && (
            <p className="text-xs text-warning">
              Descuento de {formatMoney(discount, currency)} sobre el precio de lista ({formatMoney(plan.price, currency)}).
            </p>
          )}
          {plan && amountTouched.current && discount === 0 && amountNumber !== null && listPrice !== null && amountNumber !== listPrice && (
            <p className="text-xs text-muted-foreground">Monto mayor al precio de lista ({formatMoney(plan.price, currency)}).</p>
          )}
          <FieldError message={errors.amount?.message} />
        </div>

        {/* ── Método ── */}
        <div className="space-y-1.5">
          <Label htmlFor="method">Método de pago</Label>
          <Select id="method" aria-invalid={Boolean(errors.method)} {...register("method")}>
            {PAYMENT_METHODS.map((m) => <option key={m} value={m}>{PAYMENT_METHOD_LABELS[m]}</option>)}
          </Select>
          <FieldError message={errors.method?.message} />
        </div>

        {/* ── Referencia ── */}
        <div className="space-y-1.5">
          <Label htmlFor="reference">
            Referencia {needsReference ? <span className="text-destructive">*</span> : <span className="text-muted-foreground">(opcional)</span>}
          </Label>
          <Input id="reference" autoComplete="off"
            placeholder={method === "sinpe" ? "N.º de comprobante SINPE" : method === "tarjeta" ? "N.º de autorización" : "N.º de referencia"}
            aria-invalid={Boolean(errors.reference)} className={invalid(errors.reference)} {...register("reference")} />
          <FieldError message={errors.reference?.message} />
        </div>

        {/* ── Fecha ── */}
        <div className="space-y-1.5">
          <Label htmlFor="payment_date">Fecha del pago</Label>
          <Input id="payment_date" type="date" max={todayISO()} aria-invalid={Boolean(errors.payment_date)}
            className={cn("[color-scheme:dark]", invalid(errors.payment_date))} {...register("payment_date")} />
          {paymentDate && paymentDate < todayISO() && (
            <p className="text-xs text-muted-foreground">Cobro con fecha anterior: se sumará a la caja de ese día.</p>
          )}
          <FieldError message={errors.payment_date?.message} />
        </div>
      </div>

      {/* ── Vista previa del periodo ── */}
      {plan && selected && period && (
        <div className="flex items-start gap-3 rounded-lg border border-gold/30 bg-gold/5 p-3 text-sm">
          <CalendarRange className="mt-0.5 h-4 w-4 shrink-0 text-gold" aria-hidden />
          <div>
            <p className="text-foreground">
              Nuevo periodo estimado: <strong>{formatDate(period.start)}</strong> al <strong>{formatDate(period.end)}</strong>
            </p>
            <p className="text-xs text-muted-foreground">
              {period.extendsCurrent
                ? "El socio aún tiene membresía vigente: el nuevo periodo empieza al día siguiente de su vencimiento, sin perder días."
                : "El periodo empieza en la fecha del pago."}
            </p>
          </div>
        </div>
      )}

      <div className="space-y-1.5">
        <Label htmlFor="notes">Notas <span className="text-muted-foreground">(opcional)</span></Label>
        <Textarea id="notes" rows={2} aria-invalid={Boolean(errors.notes)} className={invalid(errors.notes)}
          placeholder="Motivo del descuento, observaciones…" {...register("notes")} />
        <FieldError message={errors.notes?.message} />
      </div>

      {duplicate && (
        <Alert variant="warning" icon={<AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>¿Posible cobro duplicado?</AlertTitle>
          <AlertDescription>{duplicate}</AlertDescription>
          <div className="flex flex-wrap gap-2 pt-2">
            <Button type="button" size="sm" variant="gold" loading={confirming} onClick={() => void confirmDuplicate()}>
              Sí, registrar otro cobro
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={onClose} disabled={confirming}>
              No, cancelar
            </Button>
          </div>
        </Alert>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={busy}>Cancelar</Button>
        <Button type="submit" variant="gold" loading={isSubmitting} disabled={busy || Boolean(duplicate)}>
          {amountNumber !== null ? `Cobrar ${formatMoney(amountNumber, currency)}` : "Registrar cobro"}
        </Button>
      </DialogFooter>
    </form>
  );
}
