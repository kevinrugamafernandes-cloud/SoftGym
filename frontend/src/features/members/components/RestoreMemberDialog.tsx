import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { useNavigate } from "react-router-dom";
import { z } from "zod";
import { AlertCircle, Info, Search, UserCheck } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/common/Spinner";
import { useCedulaLookup, useRestoreMember } from "@/hooks/useMembers";
import { toast } from "@/hooks/useToast";
import { reportError } from "@/lib/report-error";
import { deriveLookupState } from "../lookup-state";
import { isLookupEligible, normalizeIdentification } from "../schemas";

const searchSchema = z.object({
  identification: z
    .string()
    .trim()
    .refine(isLookupEligible, "Ingrese una cédula o DIMEX de 9 a 12 dígitos, solo números"),
});
type SearchValues = z.infer<typeof searchSchema>;

interface RestoreMemberDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Restaura a un socio dado de baja. El listado de socios no muestra a los dados de baja,
 * así que se localizan por cédula (el backend indica si la cédula pertenece a un socio de baja).
 */
export function RestoreMemberDialog({ open, onOpenChange }: RestoreMemberDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Restaurar socio</DialogTitle>
          <DialogDescription>
            Busque por cédula a un socio dado de baja para devolverlo al sistema con su historial.
          </DialogDescription>
        </DialogHeader>
        <RestoreForm onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  );
}

function RestoreForm({ onClose }: { onClose: () => void }) {
  const navigate = useNavigate();
  const restore = useRestoreMember();
  const [requested, setRequested] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const { register, handleSubmit, watch, formState: { errors } } = useForm<SearchValues>({
    resolver: zodResolver(searchSchema),
    defaultValues: { identification: "" },
  });

  const current = normalizeIdentification(watch("identification") ?? "");
  const lookup = useCedulaLookup(requested);
  const state = deriveLookupState(requested, current, lookup);

  const onSearch = (values: SearchValues) => {
    setActionError(null);
    const next = normalizeIdentification(values.identification);
    if (next === requested) void lookup.refetch();
    else setRequested(next);
  };

  const onRestore = async (id: string) => {
    setActionError(null);
    try {
      const restored = await restore.mutateAsync(id);
      toast({
        variant: "success",
        title: "Socio restaurado",
        description: `${restored.full_name} fue restaurado y quedó inactivo. Actívelo desde su ficha.`,
      });
      onClose();
      navigate(`/members/${restored.id}`);
    } catch (err) {
      setActionError(reportError(err, "No se pudo restaurar el socio"));
    }
  };

  return (
    <form onSubmit={handleSubmit(onSearch)} noValidate className="space-y-4">
      <div className="space-y-1.5">
        <Label htmlFor="restore-identification">Cédula del socio</Label>
        <div className="flex gap-2">
          <Input
            id="restore-identification" autoComplete="off" placeholder="1-1234-5678"
            aria-invalid={Boolean(errors.identification)} {...register("identification")}
          />
          <Button type="submit" variant="outline" disabled={state.kind === "loading"}>
            <Search className="mr-2 h-4 w-4" aria-hidden /> Buscar
          </Button>
        </div>
        {errors.identification && <p className="text-xs text-destructive">{errors.identification.message}</p>}
      </div>

      {state.kind === "loading" && (
        <Alert variant="info" icon={<Spinner className="mt-0.5 shrink-0" />}>
          <AlertTitle>Buscando…</AlertTitle>
        </Alert>
      )}

      {state.kind === "registered" && state.data.existing_member_deleted && (
        <Alert variant="warning" icon={<UserCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>{state.data.full_name}</AlertTitle>
          <AlertDescription>Está dado de baja. Al restaurarlo quedará como «inactivo».</AlertDescription>
          <Button
            type="button" size="sm" variant="gold" className="mt-1" loading={restore.isPending}
            onClick={() => void onRestore(state.data.existing_member_id as string)}
          >
            Restaurar socio
          </Button>
        </Alert>
      )}

      {state.kind === "registered" && !state.data.existing_member_deleted && (
        <Alert variant="info" icon={<Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>{state.data.full_name} no está dado de baja</AlertTitle>
          <AlertDescription>Es un socio vigente; no necesita restauración.</AlertDescription>
          <Button
            type="button" size="sm" variant="outline" className="mt-1"
            onClick={() => { onClose(); navigate(`/members/${state.data.existing_member_id}`); }}
          >
            Ver ficha
          </Button>
        </Alert>
      )}

      {(state.kind === "found" || state.kind === "not_found") && (
        <Alert variant="info" icon={<Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>No hay un socio registrado con esa cédula</AlertTitle>
          <AlertDescription>Puede registrarlo como socio nuevo desde «Nuevo socio».</AlertDescription>
        </Alert>
      )}

      {state.kind === "unavailable" && (
        <Alert variant="warning" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>No se pudo completar la búsqueda</AlertTitle>
          <AlertDescription>El servicio no está disponible en este momento. Intente de nuevo en unos minutos.</AlertDescription>
        </Alert>
      )}

      {state.kind === "rejected" && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{state.message}</AlertDescription>
        </Alert>
      )}

      {actionError && (
        <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertDescription className="text-foreground">{actionError}</AlertDescription>
        </Alert>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onClose}>Cerrar</Button>
      </DialogFooter>
    </form>
  );
}
