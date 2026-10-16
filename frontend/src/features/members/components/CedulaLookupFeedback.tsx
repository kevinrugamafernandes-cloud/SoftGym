import { AlertTriangle, CheckCircle2, Info, RefreshCw, UserCheck, XCircle } from "lucide-react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/common/Spinner";
import type { LookupUiState } from "../lookup-state";

interface CedulaLookupFeedbackProps {
  state: LookupUiState;
  /** Puede restaurar socios dados de baja (solo administradores). */
  canRestore: boolean;
  onRetry: () => void;
  onRestore: (memberId: string) => void;
  restoring: boolean;
  restoreError: string | null;
  /** Revisión manual del orden nombre/apellidos (cuando needs_review = true). */
  reviewConfirmed: boolean;
  reviewError: boolean;
  onReviewChange: (confirmed: boolean) => void;
  /** Nota cuando el autocompletado respetó datos que el usuario ya había escrito. */
  autofillNote: string | null;
}

export function CedulaLookupFeedback({
  state, canRestore, onRetry, onRestore, restoring, restoreError,
  reviewConfirmed, reviewError, onReviewChange, autofillNote,
}: CedulaLookupFeedbackProps) {
  switch (state.kind) {
    case "idle":
      return null;

    case "loading":
      return (
        <Alert variant="info" icon={<Spinner className="mt-0.5 shrink-0" />}>
          <AlertTitle>Consultando en Hacienda…</AlertTitle>
          <AlertDescription>Puede seguir completando el formulario mientras tanto.</AlertDescription>
        </Alert>
      );

    case "found":
      return (
        <div className="space-y-2">
          <Alert variant="success" icon={<CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
            <AlertTitle>Datos encontrados y autocompletados</AlertTitle>
            <AlertDescription>
              Registrado en Hacienda como <strong className="text-foreground">{state.data.full_name}</strong>.
              Hacienda no entrega la fecha de nacimiento: ingrésela manualmente.
              {autofillNote && <span className="mt-1 block">{autofillNote}</span>}
            </AlertDescription>
          </Alert>

          {state.data.needs_review && (
            <Alert variant="warning" icon={<AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
              <AlertTitle>Revise el nombre y los apellidos</AlertTitle>
              <AlertDescription>
                Hacienda entrega el nombre completo en un solo campo, por lo que la separación entre
                nombre y apellidos es una aproximación. Compárela con «{state.data.full_name}» y corrija
                el orden si hace falta.
              </AlertDescription>
              <label className="mt-2 flex cursor-pointer items-start gap-2 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={reviewConfirmed}
                  onChange={(e) => onReviewChange(e.target.checked)}
                  aria-invalid={reviewError}
                  aria-describedby={reviewError ? "review-error" : undefined}
                  className="mt-0.5 h-4 w-4 shrink-0 accent-gold"
                />
                <span>Confirmo que revisé el nombre y los apellidos.</span>
              </label>
              {reviewError && (
                <p id="review-error" className="text-xs text-destructive">
                  Confirme que revisó el orden de nombre y apellidos antes de guardar.
                </p>
              )}
            </Alert>
          )}
        </div>
      );

    case "registered": {
      const { data } = state;
      return (
        <Alert variant="warning" icon={<UserCheck className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>
            {data.existing_member_deleted ? "Este socio está dado de baja" : "Este socio ya está registrado"}
          </AlertTitle>
          <AlertDescription>
            La cédula pertenece a <strong className="text-foreground">{data.full_name}</strong>.
            {data.existing_member_deleted
              ? canRestore
                ? " Puede restaurarlo en lugar de crear un registro nuevo."
                : " Pida a un administrador que lo restaure."
              : " No se puede registrar dos veces."}
          </AlertDescription>
          {restoreError && <p className="text-xs text-destructive">{restoreError}</p>}
          <div className="flex flex-wrap gap-2 pt-1">
            {!data.existing_member_deleted && data.existing_member_id && (
              <Button asChild size="sm" variant="outline">
                <Link to={`/members/${data.existing_member_id}`}>Ver ficha del socio</Link>
              </Button>
            )}
            {data.existing_member_deleted && canRestore && data.existing_member_id && (
              <Button
                type="button" size="sm" variant="gold" loading={restoring}
                onClick={() => onRestore(data.existing_member_id as string)}
              >
                Restaurar socio
              </Button>
            )}
          </div>
        </Alert>
      );
    }

    case "not_found":
      return (
        <Alert variant="info" icon={<Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>No se encontró esa cédula en Hacienda</AlertTitle>
          <AlertDescription>
            La consulta solo incluye personas inscritas como contribuyentes. Ingrese los datos manualmente.
          </AlertDescription>
        </Alert>
      );

    case "unavailable":
      return (
        <Alert variant="warning" icon={<AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>El servicio de consulta no está disponible</AlertTitle>
          <AlertDescription>
            No se pudo consultar a Hacienda en este momento. El formulario sigue habilitado:
            ingrese los datos manualmente o reintente más tarde.
          </AlertDescription>
          <Button type="button" size="sm" variant="outline" className="mt-1" onClick={onRetry}>
            <RefreshCw className="mr-2 h-3.5 w-3.5" aria-hidden /> Reintentar
          </Button>
        </Alert>
      );

    case "rejected":
      return (
        <Alert variant="destructive" icon={<XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}>
          <AlertTitle>No se pudo usar la consulta automática</AlertTitle>
          <AlertDescription>{state.message}</AlertDescription>
        </Alert>
      );
  }
}
