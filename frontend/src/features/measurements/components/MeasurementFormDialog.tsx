import { useEffect, useState } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, ChevronDown } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useCreateMeasurement, useUpdateMeasurement } from "@/hooks/useMeasurements";
import { toast } from "@/hooks/useToast";
import { getFieldErrors } from "@/lib/axios";
import { formatNumber, trimDecimal } from "@/lib/numbers";
import { describeInvalidFields } from "@/lib/form-errors";
import { reportError } from "@/lib/report-error";
import { cn } from "@/utils";
import { todayISO } from "@/features/members/schemas";
import type { Measurement } from "@/types";

import {
  OPTIONAL_FIELDS, convertHeight, emptyMeasurementForm, measurementSchema, measurementToForm,
  toCreatePayload, toUpdatePayload, type MeasurementFormValues,
} from "../schemas";

interface MeasurementFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  memberId: string;
  memberName: string;
  mode: "create" | "edit";
  /** Requerido en modo "edit". */
  measurement?: Measurement;
  /** Estatura de la última medición (cm): se precarga porque casi no cambia. */
  defaultHeightCm?: string | null;
  onSaved?: (measurement: Measurement) => void;
}

export function MeasurementFormDialog({ open, onOpenChange, memberName, ...rest }: MeasurementFormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{rest.mode === "create" ? "Registrar medición" : "Editar medición"}</DialogTitle>
          <DialogDescription>
            Ficha física de {memberName}. El IMC y su clasificación los calcula el sistema al guardar.
          </DialogDescription>
        </DialogHeader>
        <MeasurementForm {...rest} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

const OPTIONAL_LABELS: Record<(typeof OPTIONAL_FIELDS)[number], string> = {
  body_fat_pct: "% de grasa",
  muscle_pct: "% de músculo",
  chest_cm: "Pecho (cm)",
  waist_cm: "Cintura (cm)",
  hips_cm: "Cadera (cm)",
  arms_cm: "Brazo (cm)",
  thighs_cm: "Muslo (cm)",
  calves_cm: "Pantorrilla (cm)",
};

function MeasurementForm({
  mode, memberId, measurement, defaultHeightCm, onSaved, onClose,
}: Omit<MeasurementFormDialogProps, "open" | "onOpenChange" | "memberName"> & { onClose: () => void }) {
  const create = useCreateMeasurement(memberId);
  const update = useUpdateMeasurement(memberId);

  const initial: MeasurementFormValues = measurement
    ? measurementToForm(measurement)
    : { ...emptyMeasurementForm, height: trimDecimal(defaultHeightCm) };

  const {
    register, handleSubmit, setValue, getValues, setError, watch,
    formState: { errors, isSubmitting },
  } = useForm<MeasurementFormValues>({ resolver: zodResolver(measurementSchema), defaultValues: initial });

  const [formError, setFormError] = useState<string | null>(null);
  const [showOptional, setShowOptional] = useState(() => OPTIONAL_FIELDS.some((f) => initial[f] !== ""));
  const unit = watch("height_unit");

  // Si un campo opcional tiene error, se despliega la sección para que se vea.
  useEffect(() => {
    if (OPTIONAL_FIELDS.some((f) => errors[f])) setShowOptional(true);
  }, [errors]);

  const switchUnit = (next: "cm" | "m") => {
    if (next === unit) return;
    setValue("height", convertHeight(getValues("height"), unit, next), { shouldValidate: false });
    setValue("height_unit", next);
  };

  const onSubmit = async (values: MeasurementFormValues) => {
    setFormError(null);
    try {
      const saved =
        mode === "edit" && measurement
          ? await update.mutateAsync({ id: measurement.id, payload: toUpdatePayload(values) })
          : await create.mutateAsync(toCreatePayload(values));

      // IMC y clasificación vienen del servidor.
      const bmi = saved.bmi ? `IMC ${formatNumber(saved.bmi, { min: 1 })}` : "Sin IMC";
      toast({
        variant: "success",
        title: mode === "edit" ? "Medición actualizada" : "Medición registrada",
        description: saved.bmi_category ? `${bmi} · ${saved.bmi_category}` : bmi,
      });
      onSaved?.(saved);
      onClose();
    } catch (err) {
      setFormError(reportError(err, mode === "edit" ? "No se pudo actualizar la medición" : "No se pudo registrar la medición"));
      for (const fe of getFieldErrors(err)) {
        const known: Record<string, keyof MeasurementFormValues> = {
          height_cm: "height", recorded_at: "recorded_on", weight_kg: "weight_kg", notes: "notes",
          ...Object.fromEntries(OPTIONAL_FIELDS.map((f) => [f, f])),
        };
        const field = known[fe.field];
        if (field) setError(field, { type: "server", message: fe.message });
      }
    }
  };

  const onInvalid = (invalidFields: FieldErrors<MeasurementFormValues>) => setFormError(describeInvalidFields(invalidFields));

  const bad = (e: unknown) => (e ? "border-destructive focus-visible:ring-destructive" : undefined);

  return (
    <form onSubmit={handleSubmit(onSubmit, onInvalid)} noValidate className="space-y-4">
      {formError && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{formError}</AlertDescription>
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <div className="flex min-h-[26px] items-center"><Label htmlFor="weight_kg">Peso (kg)</Label></div>
          <Input id="weight_kg" inputMode="decimal" autoComplete="off" placeholder="82,5"
            aria-invalid={Boolean(errors.weight_kg)} className={bad(errors.weight_kg)} {...register("weight_kg")} />
          {errors.weight_kg && <p className="text-xs text-destructive">{errors.weight_kg.message}</p>}
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor="height">Estatura</Label>
            <div role="group" aria-label="Unidad de estatura" className="inline-flex rounded-md border border-border p-0.5 text-xs">
              {(["cm", "m"] as const).map((u) => (
                <button
                  key={u} type="button" onClick={() => switchUnit(u)} aria-pressed={unit === u}
                  className={cn(
                    "rounded px-2.5 py-1 font-medium transition-colors",
                    unit === u ? "bg-gold text-background" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {u}
                </button>
              ))}
            </div>
          </div>
          <Input id="height" inputMode="decimal" autoComplete="off" placeholder={unit === "cm" ? "175" : "1,75"}
            aria-invalid={Boolean(errors.height)} className={bad(errors.height)} {...register("height")} />
          {errors.height && <p className="text-xs text-destructive">{errors.height.message}</p>}
        </div>

        {mode === "create" && (
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="recorded_on">Fecha de la medición</Label>
            <Input id="recorded_on" type="date" max={todayISO()} aria-invalid={Boolean(errors.recorded_on)}
              className={cn("[color-scheme:dark] sm:max-w-[14rem]", bad(errors.recorded_on))} {...register("recorded_on")} />
            <p className="text-xs text-muted-foreground">Opcional. Si la deja vacía se registra ahora; útil para pasar fichas en papel.</p>
            {errors.recorded_on && <p className="text-xs text-destructive">{errors.recorded_on.message}</p>}
          </div>
        )}
      </div>

      {/* Composición corporal y medidas: opcional, plegable */}
      <div className="rounded-lg border border-border">
        <button
          type="button" onClick={() => setShowOptional((v) => !v)} aria-expanded={showOptional}
          className="flex w-full items-center justify-between px-3 py-2.5 text-sm font-medium"
        >
          Composición corporal y medidas (opcional)
          <ChevronDown className={cn("h-4 w-4 text-muted-foreground transition-transform", showOptional && "rotate-180")} aria-hidden />
        </button>
        {showOptional && (
          <div className="grid gap-4 border-t border-border p-3 sm:grid-cols-2">
            {OPTIONAL_FIELDS.map((f) => (
              <div key={f} className="space-y-1.5">
                <Label htmlFor={f}>{OPTIONAL_LABELS[f]}</Label>
                <Input id={f} inputMode="decimal" autoComplete="off" aria-invalid={Boolean(errors[f])}
                  className={bad(errors[f])} {...register(f)} />
                {errors[f] && <p className="text-xs text-destructive">{errors[f]?.message}</p>}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="measurement-notes">Notas</Label>
        <Textarea id="measurement-notes" rows={2} aria-invalid={Boolean(errors.notes)} className={bad(errors.notes)} {...register("notes")} />
        {errors.notes && <p className="text-xs text-destructive">{errors.notes.message}</p>}
      </div>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Cancelar</Button>
        <Button type="submit" variant="gold" loading={isSubmitting}>
          {mode === "create" ? "Guardar medición" : "Guardar cambios"}
        </Button>
      </DialogFooter>
    </form>
  );
}
