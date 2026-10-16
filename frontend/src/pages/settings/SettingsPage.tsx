import { useState } from "react";
import { useForm, type FieldErrors } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertCircle, Building2, MessageSquareText, Pencil, Plus, Power, Tags } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { TAX_RATES } from "@/features/pos/schemas";
import { useGymSettings, useUpdateSettings } from "@/hooks/useAdmin";
import { useCreatePlan, usePlans, useUpdatePlan } from "@/hooks/usePlans";
import { toast } from "@/hooks/useToast";
import { getErrorMessage, getFieldErrors } from "@/lib/axios";
import { describeInvalidFields } from "@/lib/form-errors";
import { formatMoney } from "@/lib/money";
import { isDecimal, normalizeDecimal, trimDecimal } from "@/lib/numbers";
import { reportError } from "@/lib/report-error";
import { cn } from "@/utils";
import type { GymSettings, Plan } from "@/types";

// ── Datos del negocio y mensajes ──────────────────────────────────────────────
const VARS = ["nombre", "gimnasio", "plan", "fecha_vencimiento", "dias", "telefono"];
const unknownVar = (v: string) => (v.match(/\{([^}]*)\}/g) ?? []).map((x) => x.slice(1, -1)).find((x) => !VARS.includes(x));
const template = (label: string) =>
  z.string().trim().min(1, `El mensaje de ${label} no puede quedar vacío`).max(1000, "Máximo 1000 caracteres")
    .refine((v) => (v.match(/\{/g) ?? []).length === (v.match(/\}/g) ?? []).length, "Hay llaves { } sin cerrar")
    .refine((v) => !unknownVar(v), (v) => ({ message: `Variable desconocida: {${unknownVar(v)}}` }));

const settingsSchema = z.object({
  name: z.string().trim().min(2, "Mínimo 2 caracteres").max(120),
  legal_name: z.string().trim().max(160),
  tax_id: z.string().trim().refine((v) => v === "" || /^\d{9,12}$/.test(v.replace(/[\s-]/g, "")), "La cédula tiene de 9 a 12 dígitos"),
  whatsapp_phone: z.string().trim().refine((v) => v === "" || v.replace(/\D/g, "").length >= 8, "Teléfono inválido (8 dígitos)"),
  email: z.string().trim().refine((v) => v === "" || z.string().email().safeParse(v).success, "Correo inválido"),
  address: z.string().trim().max(500),
  receipt_message: z.string().trim().max(300),
  overdue_message: template("membresía vencida"),
  expiring_message: template("membresía por vencer"),
});
type SettingsValues = z.infer<typeof settingsSchema>;
const FIELDS = Object.keys(settingsSchema.shape) as (keyof SettingsValues)[];

const toForm = (s: GymSettings): SettingsValues => ({
  name: s.name, legal_name: s.legal_name ?? "", tax_id: s.tax_id ?? "", whatsapp_phone: s.whatsapp_phone ?? "",
  email: s.email ?? "", address: s.address ?? "", receipt_message: s.receipt_message ?? "",
  overdue_message: s.overdue_message, expiring_message: s.expiring_message,
});

/** Vista previa con datos de ejemplo. */
function preview(text: string, gym: string, phone: string, vencida: boolean): string {
  const values: Record<string, string> = {
    nombre: "Laura", gimnasio: gym || "Lion Fitness Center", plan: "Mensualidad",
    fecha_vencimiento: "15/10/2026", dias: vencida ? "hace 3 días" : "en 2 días", telefono: phone,
  };
  return text.replace(/\{([^}]+)\}/g, (m, k: string) => values[k] ?? m);
}

function BusinessForm({ settings }: { settings: GymSettings }) {
  const update = useUpdateSettings();
  const [formError, setFormError] = useState<string | null>(null);
  const { register, handleSubmit, watch, setError, formState: { errors, isSubmitting, isDirty }, reset } = useForm<SettingsValues>({
    resolver: zodResolver(settingsSchema), defaultValues: toForm(settings),
  });
  const [name, phone, overdue, expiring] = watch(["name", "whatsapp_phone", "overdue_message", "expiring_message"]);

  const onSubmit = async (v: SettingsValues) => {
    setFormError(null);
    try {
      const saved = await update.mutateAsync({
        name: v.name, legal_name: v.legal_name || null, tax_id: v.tax_id || null, whatsapp_phone: v.whatsapp_phone || null,
        email: v.email || null, address: v.address || null, receipt_message: v.receipt_message || null,
        overdue_message: v.overdue_message, expiring_message: v.expiring_message,
      });
      reset(toForm(saved));
      toast({ variant: "success", title: "Configuración guardada", description: "Los comprobantes y mensajes usarán los datos nuevos." });
    } catch (err) {
      setFormError(reportError(err, "No se pudo guardar la configuración"));
      for (const fe of getFieldErrors(err)) {
        if ((FIELDS as string[]).includes(fe.field)) setError(fe.field as keyof SettingsValues, { type: "server", message: fe.message });
      }
    }
  };

  const field = (id: keyof SettingsValues, label: string, opts: { placeholder?: string; type?: string; hint?: string; className?: string } = {}) => (
    <div className={cn("space-y-1.5", opts.className)}>
      <Label htmlFor={`s-${id}`}>{label}</Label>
      <Input id={`s-${id}`} type={opts.type} autoComplete="off" placeholder={opts.placeholder} aria-invalid={Boolean(errors[id])}
        className={errors[id] ? "border-destructive focus-visible:ring-destructive" : undefined} {...register(id)} />
      {errors[id] ? <p className="text-xs text-destructive">{errors[id]?.message}</p> : opts.hint && <p className="text-xs text-muted-foreground">{opts.hint}</p>}
    </div>
  );

  const area = (id: "overdue_message" | "expiring_message", label: string, sample: string) => (
    <div className="space-y-1.5">
      <Label htmlFor={`s-${id}`}>{label}</Label>
      <Textarea id={`s-${id}`} rows={3} aria-invalid={Boolean(errors[id])}
        className={errors[id] ? "border-destructive focus-visible:ring-destructive" : undefined} {...register(id)} />
      {errors[id] && <p className="text-xs text-destructive">{errors[id]?.message}</p>}
      <p className="rounded-md border border-success/30 bg-success/5 p-2 text-xs text-muted-foreground">
        <span className="font-medium text-success">Vista previa: </span>{sample}
      </p>
    </div>
  );

  return (
    <form onSubmit={handleSubmit(onSubmit, (f: FieldErrors<SettingsValues>) => setFormError(describeInvalidFields(f)))} noValidate className="space-y-6">
      {formError && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{formError}</AlertDescription>
        </Alert>
      )}
      <Card>
        <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2 text-base"><Building2 className="h-4 w-4 text-gold" aria-hidden /> Datos del negocio</CardTitle></CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          {field("name", "Nombre del gimnasio")}
          {field("whatsapp_phone", "WhatsApp comercial", { placeholder: "8888-1234", type: "tel", hint: "Aparece en comprobantes y recordatorios ({telefono})" })}
          {field("legal_name", "Razón social", { placeholder: "Opcional" })}
          {field("tax_id", "Cédula física o jurídica", { placeholder: "3-101-123456" })}
          {field("email", "Correo", { type: "email", placeholder: "Opcional" })}
          {field("address", "Dirección", { placeholder: "Provincia, cantón, señas" })}
          {field("receipt_message", "Mensaje al pie de comprobantes", { className: "sm:col-span-2", placeholder: "¡Gracias por entrenar con nosotros!" })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-base"><MessageSquareText className="h-4 w-4 text-gold" aria-hidden /> Mensajes de WhatsApp</CardTitle>
          <p className="text-sm text-muted-foreground">
            Variables: {VARS.map((v) => <code key={v} className="mr-1 rounded bg-muted px-1 py-0.5 text-xs text-foreground">{`{${v}}`}</code>)}
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {area("overdue_message", "Recordatorio — membresía vencida", preview(overdue ?? "", name ?? "", phone ?? "", true))}
          {area("expiring_message", "Recordatorio — membresía por vencer", preview(expiring ?? "", name ?? "", phone ?? "", false))}
        </CardContent>
      </Card>

      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" disabled={!isDirty || isSubmitting} onClick={() => reset(toForm(settings))}>Descartar cambios</Button>
        <Button type="submit" variant="gold" loading={isSubmitting} disabled={!isDirty}>Guardar configuración</Button>
      </div>
    </form>
  );
}

// ── Planes ────────────────────────────────────────────────────────────────────
const planSchema = z.object({
  name: z.string().trim().min(2, "Mínimo 2 caracteres").max(100),
  duration_days: z.string().trim().refine((v) => /^\d{1,4}$/.test(v) && Number(v) >= 1 && Number(v) <= 3650, "Entre 1 y 3650 días"),
  price: z.string().trim().refine((v) => isDecimal(v), "Precio inválido"),
  tax_rate: z.enum(["13", "4", "2", "1", "0"]),
  description: z.string().trim().max(500),
});
type PlanValues = z.infer<typeof planSchema>;

function PlanDialog({ plan, open, onOpenChange }: { plan?: Plan; open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreatePlan();
  const update = useUpdatePlan();
  const [error, setError] = useState<string | null>(null);
  const rate = plan ? String(Number(plan.tax_rate)) : "13";
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<PlanValues>({
    resolver: zodResolver(planSchema),
    values: plan
      ? { name: plan.name, duration_days: String(plan.duration_days), price: trimDecimal(plan.price),
          tax_rate: (["13", "4", "2", "1", "0"].includes(rate) ? rate : "13") as PlanValues["tax_rate"], description: plan.description ?? "" }
      : { name: "", duration_days: "30", price: "", tax_rate: "13", description: "" },
  });
  const onSubmit = async (v: PlanValues) => {
    setError(null);
    const payload = { name: v.name, duration_days: Number(v.duration_days), price: normalizeDecimal(v.price), tax_rate: v.tax_rate,
      description: v.description || null };
    try {
      if (plan) await update.mutateAsync({ id: plan.id, payload });
      else await create.mutateAsync(payload);
      toast({ variant: "success", title: plan ? "Plan actualizado" : "Plan creado", description: v.name });
      onOpenChange(false);
    } catch (err) {
      setError(reportError(err, "No se pudo guardar el plan"));
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>{plan ? "Editar plan" : "Nuevo plan"}</DialogTitle>
          <DialogDescription>El precio es el final al socio, con IVA incluido. Los cobros anteriores no cambian.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          {error && <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}><AlertDescription className="text-foreground">{error}</AlertDescription></Alert>}
          <div className="space-y-1.5">
            <Label htmlFor="pl-name">Nombre</Label>
            <Input id="pl-name" autoFocus {...register("name")} />
            {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="pl-days">Días</Label>
              <Input id="pl-days" inputMode="numeric" {...register("duration_days")} />
              {errors.duration_days && <p className="text-xs text-destructive">{errors.duration_days.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pl-price">Precio (₡)</Label>
              <Input id="pl-price" inputMode="decimal" className="tabular-nums" {...register("price")} />
              {errors.price && <p className="text-xs text-destructive">{errors.price.message}</p>}
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="pl-tax">IVA</Label>
              <Select id="pl-tax" {...register("tax_rate")}>{TAX_RATES.map((t) => <option key={t.value} value={t.value}>{t.value === "0" ? "Exento" : `${t.value} %`}</option>)}</Select>
            </div>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="pl-desc">Descripción <span className="text-muted-foreground">(opcional)</span></Label>
            <Input id="pl-desc" {...register("description")} />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>Cancelar</Button>
            <Button type="submit" variant="gold" loading={isSubmitting}>{plan ? "Guardar" : "Crear plan"}</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function PlansCard({ currency }: { currency: string }) {
  const plans = usePlans(false);
  const update = useUpdatePlan();
  const [editing, setEditing] = useState<Plan | "new" | null>(null);
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="flex items-center gap-2 text-base"><Tags className="h-4 w-4 text-gold" aria-hidden /> Planes de membresía</CardTitle>
        <Button size="sm" variant="gold" onClick={() => setEditing("new")}><Plus className="mr-1.5 h-4 w-4" aria-hidden /> Nuevo plan</Button>
      </CardHeader>
      <CardContent>
        {plans.isLoading ? <Skeleton className="h-32" /> : plans.isError ? (
          <ErrorMessage title="No se pudieron cargar los planes" message={getErrorMessage(plans.error)} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead>Plan</TableHead><TableHead className="text-right">Duración</TableHead>
                <TableHead className="text-right">Precio</TableHead><TableHead>Estado</TableHead>
                <TableHead className="w-24"><span className="sr-only">Acciones</span></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {plans.data?.map((p) => (
                <TableRow key={p.id} className={cn(!p.is_active && "opacity-60")}>
                  <TableCell><p className="font-medium text-foreground">{p.name}</p>{p.description && <p className="text-xs text-muted-foreground">{p.description}</p>}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.duration_days} {p.duration_days === 1 ? "día" : "días"}</TableCell>
                  <TableCell className="text-right">
                    <p className="font-medium tabular-nums">{formatMoney(p.price, currency)}</p>
                    <p className="text-xs text-muted-foreground">{Number(p.tax_rate) > 0 ? `IVA ${Number(p.tax_rate)} % incl.` : "Exento"}</p>
                  </TableCell>
                  <TableCell>{p.is_active ? <Badge variant="success">Activo</Badge> : <Badge variant="outline" className="text-muted-foreground">Inactivo</Badge>}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-0.5">
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" onClick={() => setEditing(p)}
                        aria-label={`Editar ${p.name}`} title="Editar"><Pencil className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8 text-muted-foreground hover:text-foreground" disabled={update.isPending}
                        onClick={() => update.mutate({ id: p.id, payload: { is_active: !p.is_active } }, {
                          onSuccess: () => toast({ variant: "success", title: p.is_active ? "Plan desactivado" : "Plan activado", description: p.name }),
                          onError: (err) => reportError(err, "No se pudo actualizar el plan"),
                        })}
                        aria-label={`${p.is_active ? "Desactivar" : "Activar"} ${p.name}`} title={p.is_active ? "Desactivar (no se ofrece al cobrar)" : "Activar"}>
                        <Power className={cn("h-4 w-4", !p.is_active && "text-success")} />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      <PlanDialog open={editing !== null} plan={editing && editing !== "new" ? editing : undefined} onOpenChange={(o) => !o && setEditing(null)} />
    </Card>
  );
}

export function SettingsPage() {
  const settings = useGymSettings();
  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-semibold text-foreground">Configuración</h2>
        <p className="mt-1 text-sm text-muted-foreground">Datos del negocio, mensajes personalizados y planes de membresía.</p>
      </div>
      {settings.isLoading ? <Skeleton className="h-96" /> : settings.isError || !settings.data ? (
        <div className="space-y-3">
          <ErrorMessage title="No se pudo cargar la configuración" message={getErrorMessage(settings.error)} />
          <Button variant="outline" size="sm" onClick={() => void settings.refetch()}>Reintentar</Button>
        </div>
      ) : (
        <>
          <BusinessForm key={settings.data.name + settings.data.overdue_message} settings={settings.data} />
          <PlansCard currency={settings.data.currency} />
        </>
      )}
    </div>
  );
}
