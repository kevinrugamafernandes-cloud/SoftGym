import { useEffect, useRef, useState } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { AlertCircle, Search } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { usePermissions } from "@/features/auth";
import { useCedulaLookup, useRestoreMember, useUpdateMember } from "@/hooks/useMembers";
import { useGymCurrency } from "@/hooks/usePayments";
import { ReceiptSummary } from "@/features/payments/components/ReceiptSummary";
import { toast } from "@/hooks/useToast";
import { getFieldErrors } from "@/lib/axios";
import { GENDER_LABELS, MEMBER_STATUS_LABELS } from "@/lib/labels";
import { describeInvalidFields } from "@/lib/form-errors";
import { reportError } from "@/lib/report-error";
import { cn } from "@/utils";
import type { EnrollmentResult, Gender, Member, MemberCreatePayload } from "@/types";

import { deriveLookupState } from "../lookup-state";
import {
  MEMBER_FORM_FIELDS, emptyMemberForm, isLookupEligible, isManualStatus, memberCreateSchema,
  memberEditSchema, memberToForm, normalizeIdentification, todayISO, toCreatePayload,
  toUpdatePayload, type MemberFormValues,
} from "../schemas";
import { CedulaLookupFeedback } from "./CedulaLookupFeedback";
import { EnrollPaymentStep } from "./EnrollPaymentStep";
import { MemberStatusBadge } from "./MemberStatusBadge";

interface MemberFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "create" | "edit";
  /** Requerido en modo "edit". */
  member?: Member;
}

export function MemberFormDialog({ open, onOpenChange, mode, member }: MemberFormDialogProps) {
  const navigate = useNavigate();
  const currency = useGymCurrency();
  // Inscripción en dos pasos: 1) datos del socio, 2) plan y cobro (obligatorio), 3) comprobante.
  const [step, setStep] = useState<"datos" | "cobro" | "listo">("datos");
  const [payload, setPayload] = useState<MemberCreatePayload | null>(null);
  const [backError, setBackError] = useState<{ code?: string; message: string } | null>(null);
  const [result, setResult] = useState<EnrollmentResult | null>(null);

  const title = mode === "edit" ? "Editar socio"
    : step === "datos" ? "Inscribir socio · 1 de 2" : step === "cobro" ? "Inscribir socio · 2 de 2: plan y cobro" : "Socio inscrito";
  const description = mode === "edit" ? `Modifique los datos de ${member?.full_name ?? "el socio"}.`
    : step === "datos" ? "Escriba la cédula para autocompletar con los datos de Hacienda. Luego elegirá el plan y registrará el cobro."
    : step === "cobro" ? "La inscripción se completa al registrar el primer pago: sin cobro, el socio no queda activo."
    : "La membresía quedó activa y el comprobante registrado.";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {/* El paso 1 sigue montado (oculto) en el paso 2: "Atrás" conserva lo escrito. */}
        <div className={cn(step !== "datos" && "hidden")}>
          <MemberForm mode={mode} member={member} onClose={() => onOpenChange(false)} backError={backError}
            onContinue={(p) => { setPayload(p); setBackError(null); setStep("cobro"); }} />
        </div>
        {step === "cobro" && payload && (
          <EnrollPaymentStep member={payload} currency={currency}
            onBack={(err) => { setBackError(err ?? null); setStep("datos"); }}
            onEnrolled={(r) => { setResult(r); setStep("listo"); }}
            onCreatedWithoutPayment={(m) => { onOpenChange(false); navigate(`/members/${m.id}`); }} />
        )}
        {step === "listo" && result && (
          <div className="space-y-4">
            <ReceiptSummary payment={result.payment} currency={currency} memberPhone={result.member.phone} />
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cerrar</Button>
              <Button type="button" variant="gold" onClick={() => { onOpenChange(false); navigate(`/members/${result.member.id}`); }}>
                Ver ficha del socio
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function FieldError({ message }: { message?: string }) {
  return message ? <p className="text-xs text-destructive">{message}</p> : null;
}

const invalid = (hasError: unknown) => hasError ? "border-destructive focus-visible:ring-destructive" : undefined;

function MemberForm({ mode, member, onClose, onContinue, backError }: {
  mode: "create" | "edit"; member?: Member; onClose: () => void;
  onContinue?: (payload: MemberCreatePayload) => void;
  backError?: { code?: string; message: string } | null;
}) {
  const navigate = useNavigate();
  const { can } = usePermissions();
  const updateMember = useUpdateMember();
  const restoreMember = useRestoreMember();

  const {
    register, handleSubmit, setValue, getValues, setError, watch,
    formState: { errors, isSubmitting },
  } = useForm<MemberFormValues>({
    resolver: zodResolver(mode === "create" ? memberCreateSchema : memberEditSchema),
    defaultValues: member ? memberToForm(member) : emptyMemberForm,
  });

  const [formError, setFormError] = useState<string | null>(null);
  const backErrorRef = useRef(backError);

  // ── Fácil Inscripción ──────────────────────────────────────────────────────
  const normalized = normalizeIdentification(watch("identification") ?? "");
  const [requested, setRequested] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0); // fuerza reaplicar el autocompletado en una consulta explícita
  const lookup = useCedulaLookup(mode === "create" ? requested : null);
  const lookupState = deriveLookupState(requested, normalized, lookup);
  const lookupAllowed = mode === "create" && can("members.lookup");
  const canLookup = lookupAllowed && isLookupEligible(normalized);

  const [autofillNote, setAutofillNote] = useState<string | null>(null);
  const [reviewConfirmed, setReviewConfirmed] = useState(false);
  const [reviewError, setReviewError] = useState(false);
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const autofilled = useRef({ first_name: "", last_name: "" });

  const startLookup = () => {
    if (!canLookup) return;
    setNonce((n) => n + 1);
    if (requested === normalized) void lookup.refetch();
    else setRequested(normalized);
  };

  // Autocompleta SOLO campos vacíos o que aún contienen el último autocompletado:
  // nunca pisa lo que el usuario escribió o corrigió a mano.
  const lookupData = lookup.data;
  useEffect(() => {
    if (!lookupData || lookupData.already_registered || lookupData.identification !== requested) return;
    const current = getValues();
    const last = autofilled.current;
    const canFirst = current.first_name.trim() === "" || current.first_name === last.first_name;
    const canLast = current.last_name.trim() === "" || current.last_name === last.last_name;
    const opts = { shouldDirty: true, shouldValidate: true } as const;

    if (canFirst) setValue("first_name", lookupData.first_name, opts);
    if (canLast) setValue("last_name", lookupData.last_name, opts);
    if (lookupData.birth_date && !current.birth_date) setValue("birth_date", lookupData.birth_date, opts);

    autofilled.current = {
      first_name: canFirst ? lookupData.first_name : last.first_name,
      last_name: canLast ? lookupData.last_name : last.last_name,
    };
    setAutofillNote(canFirst && canLast ? null : "Se conservaron los datos que usted ya había escrito.");
    setReviewConfirmed(false);
    setReviewError(false);
  }, [lookupData, requested, nonce, getValues, setValue]);

  // Error devuelto por el paso 2 (p. ej. la cédula ya existe): se muestra aquí y se consulta la cédula
  // para ofrecer las acciones de "ya registrado".
  useEffect(() => {
    if (!backError || backError === backErrorRef.current) return;
    backErrorRef.current = backError;
    setFormError(backError.message);
    if ((backError.code === "member_exists" || backError.code === "member_deleted") && isLookupEligible(normalized)) {
      setRequested(normalized);
      setNonce((n) => n + 1);
    }
  }, [backError, normalized]);

  const reviewActive = lookupState.kind === "found" && lookupState.data.needs_review;
  const blockedByExisting = lookupState.kind === "registered";

  const idField = register("identification");

  const handleRestore = async (id: string) => {
    setRestoreError(null);
    try {
      const restored = await restoreMember.mutateAsync(id);
      toast({
        variant: "success",
        title: "Socio restaurado",
        description: `${restored.full_name} fue restaurado y quedó inactivo. Actívelo desde su ficha.`,
      });
      onClose();
      navigate(`/members/${restored.id}`);
    } catch (err) {
      setRestoreError(reportError(err, "No se pudo restaurar el socio"));
    }
  };

  const onSubmit = async (values: MemberFormValues) => {
    setFormError(null);

    if (mode === "create" && reviewActive && !reviewConfirmed) {
      setReviewError(true);
      setFormError("Confirme que revisó el nombre y los apellidos antes de guardar.");
      return;
    }

    if (mode === "create") {
      // La inscripción NO se guarda aquí: pasa al paso 2 (plan y cobro), que crea socio + pago juntos.
      onContinue?.(toCreatePayload(values));
      return;
    }

    try {
      if (member) {
        const updated = await updateMember.mutateAsync({ id: member.id, payload: toUpdatePayload(values, member) });
        toast({ variant: "success", title: "Cambios guardados", description: `Los datos de ${updated.full_name} se actualizaron.` });
      }
      onClose();
    } catch (err) {
      setFormError(reportError(err, "No se pudieron guardar los cambios"));
      // Errores 422 por campo → se marcan en el campo correspondiente.
      for (const fe of getFieldErrors(err)) {
        if ((MEMBER_FORM_FIELDS as readonly string[]).includes(fe.field)) {
          setError(fe.field as keyof MemberFormValues, { type: "server", message: fe.message });
        }
      }
    }
  };

  // Red de seguridad: si la validación falla, SIEMPRE se avisa (incluso por un campo no visible).
  const onInvalid = (invalidFields: FieldErrors<MemberFormValues>) => setFormError(describeInvalidFields(invalidFields));

  const isEditingManualStatus = mode === "edit" && member !== undefined && isManualStatus(member.status);

  return (
    <form onSubmit={handleSubmit(onSubmit, onInvalid)} noValidate className="space-y-4">
      {formError && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{formError}</AlertDescription>
        </Alert>
      )}

      {/* ── Cédula + consulta ── */}
      <div className="space-y-1.5">
        <Label htmlFor="identification">Cédula / identificación</Label>
        <div className="flex gap-2">
          <Input
            id="identification"
            autoComplete="off"
            placeholder="1-1234-5678"
            readOnly={mode === "edit"}
            aria-invalid={Boolean(errors.identification)}
            className={cn(invalid(errors.identification), mode === "edit" && "cursor-not-allowed opacity-70")}
            {...idField}
            onBlur={(e) => {
              void idField.onBlur(e);
              // Consulta automática al pasar a OTRO campo del formulario (no al cancelar ni al ir al botón).
              const next = e.relatedTarget;
              const toAnotherField =
                next instanceof HTMLInputElement || next instanceof HTMLSelectElement || next instanceof HTMLTextAreaElement;
              if (canLookup && requested !== normalized && toAnotherField) {
                setNonce((n) => n + 1);
                setRequested(normalized);
              }
            }}
            onKeyDown={(e) => {
              // Primer ENTER: consulta. Si ya se consultó esta cédula, ENTER envía el formulario.
              if (e.key === "Enter" && canLookup && requested !== normalized) {
                e.preventDefault();
                startLookup();
              }
            }}
          />
          {lookupAllowed && (
            <Button
              type="button" variant="outline" onClick={startLookup}
              disabled={!canLookup || lookupState.kind === "loading"}
              aria-label="Consultar cédula en Hacienda" title="Consultar cédula en Hacienda"
            >
              <Search className="h-4 w-4 sm:mr-2" aria-hidden />
              <span className="hidden sm:inline">Consultar</span>
            </Button>
          )}
        </div>
        <FieldError message={errors.identification?.message} />
        {mode === "edit" && <p className="text-xs text-muted-foreground">La cédula no se puede modificar.</p>}
        {lookupAllowed && lookupState.kind === "idle" && (
          <p className="text-xs text-muted-foreground">
            {normalized && !isLookupEligible(normalized)
              ? "La consulta automática aplica a cédulas y DIMEX de 9 a 12 dígitos; para otras identificaciones ingrese los datos manualmente."
              : "Escriba la cédula y presione Enter o «Consultar» para autocompletar con los datos de Hacienda."}
          </p>
        )}
      </div>

      {mode === "create" && (
        <CedulaLookupFeedback
          state={lookupState}
          canRestore={can("members.restore")}
          onRetry={startLookup}
          onRestore={(id) => void handleRestore(id)}
          restoring={restoreMember.isPending}
          restoreError={restoreError}
          reviewConfirmed={reviewConfirmed}
          reviewError={reviewError}
          onReviewChange={(v) => { setReviewConfirmed(v); if (v) setReviewError(false); }}
          autofillNote={autofillNote}
        />
      )}

      {/* ── Datos personales ── */}
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="first_name">Nombre</Label>
          <Input id="first_name" autoComplete="off" aria-invalid={Boolean(errors.first_name)}
            className={invalid(errors.first_name)} {...register("first_name")} />
          <FieldError message={errors.first_name?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="last_name">Apellidos</Label>
          <Input id="last_name" autoComplete="off" aria-invalid={Boolean(errors.last_name)}
            className={invalid(errors.last_name)} {...register("last_name")} />
          <FieldError message={errors.last_name?.message} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="birth_date">Fecha de nacimiento</Label>
          <Input id="birth_date" type="date" max={todayISO()} aria-invalid={Boolean(errors.birth_date)}
            className={cn("[color-scheme:dark]", invalid(errors.birth_date))} {...register("birth_date")} />
          <FieldError message={errors.birth_date?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="gender">Género</Label>
          <Select id="gender" {...register("gender")}>
            <option value="">Sin especificar</option>
            {(Object.keys(GENDER_LABELS) as Gender[]).map((g) => (
              <option key={g} value={g}>{GENDER_LABELS[g]}</option>
            ))}
          </Select>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="phone">Teléfono</Label>
          <Input id="phone" type="tel" inputMode="tel" autoComplete="off" placeholder="8888-1234"
            aria-invalid={Boolean(errors.phone)} className={invalid(errors.phone)} {...register("phone")} />
          <FieldError message={errors.phone?.message} />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="email">Correo electrónico</Label>
          <Input id="email" type="email" autoComplete="off" placeholder="socio@correo.com"
            aria-invalid={Boolean(errors.email)} className={invalid(errors.email)} {...register("email")} />
          <FieldError message={errors.email?.message} />
        </div>

        {mode === "create" && (
          <div className="space-y-1.5">
            <Label htmlFor="joined_at">Fecha de ingreso</Label>
            <Input id="joined_at" type="date" max={todayISO()} aria-invalid={Boolean(errors.joined_at)}
              className={cn("[color-scheme:dark]", invalid(errors.joined_at))} {...register("joined_at")} />
            <p className="text-xs text-muted-foreground">Opcional. Si la deja vacía se usa hoy; útil para socios antiguos.</p>
            <FieldError message={errors.joined_at?.message} />
          </div>
        )}

        {mode === "edit" && member && (
          <div className="space-y-1.5">
            <Label htmlFor="status">Estado</Label>
            {isEditingManualStatus ? (
              <Select id="status" {...register("status")}>
                <option value="activo">{MEMBER_STATUS_LABELS.activo}</option>
                <option value="inactivo">{MEMBER_STATUS_LABELS.inactivo}</option>
              </Select>
            ) : (
              <div className="flex h-10 items-center gap-2">
                <MemberStatusBadge status={member.status} />
                <span className="text-xs text-muted-foreground">Lo calcula el sistema según la membresía.</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="notes">Notas internas</Label>
        <Textarea id="notes" rows={3} aria-invalid={Boolean(errors.notes)} className={invalid(errors.notes)} {...register("notes")} />
        <FieldError message={errors.notes?.message} />
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Cancelar</Button>
        <Button type="submit" variant="gold" loading={isSubmitting} disabled={blockedByExisting}>
          {mode === "create" ? "Continuar al cobro" : "Guardar cambios"}
        </Button>
      </DialogFooter>
    </form>
  );
}
