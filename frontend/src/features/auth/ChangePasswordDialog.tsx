import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertCircle } from "lucide-react";

import {
  Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "@/hooks/useToast";
import { getErrorMessage } from "@/lib/axios";
import { authService } from "@/services/auth.service";

const schema = z
  .object({
    current_password: z.string().min(1, "Indique su contraseña actual"),
    new_password: z.string().min(8, "Mínimo 8 caracteres").max(72, "Máximo 72 caracteres"),
    confirm: z.string(),
  })
  .refine((v) => v.new_password === v.confirm, { path: ["confirm"], message: "Las contraseñas no coinciden" });
type Values = z.infer<typeof schema>;

/** Cambio de la contraseña propia. Cierra las sesiones abiertas en otros equipos. */
export function ChangePasswordDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<Values>({
    resolver: zodResolver(schema), defaultValues: { current_password: "", new_password: "", confirm: "" },
  });
  const close = () => { reset(); setError(null); onOpenChange(false); };
  const onSubmit = async (v: Values) => {
    setError(null);
    try {
      await authService.changePassword(v.current_password, v.new_password);
      toast({ variant: "success", title: "Contraseña actualizada", description: "Las sesiones en otros equipos se cerraron." });
      close();
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Cambiar mi contraseña</DialogTitle>
          <DialogDescription>Las sesiones abiertas en otros equipos se cerrarán.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          {error && <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}><AlertDescription className="text-foreground">{error}</AlertDescription></Alert>}
          <div className="space-y-1.5">
            <Label htmlFor="cp-current">Contraseña actual</Label>
            <Input id="cp-current" type="password" autoFocus autoComplete="current-password" {...register("current_password")} />
            {errors.current_password && <p className="text-xs text-destructive">{errors.current_password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cp-new">Contraseña nueva</Label>
            <Input id="cp-new" type="password" autoComplete="new-password" {...register("new_password")} />
            {errors.new_password && <p className="text-xs text-destructive">{errors.new_password.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="cp-confirm">Repita la contraseña nueva</Label>
            <Input id="cp-confirm" type="password" autoComplete="new-password" {...register("confirm")} />
            {errors.confirm && <p className="text-xs text-destructive">{errors.confirm.message}</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={close} disabled={isSubmitting}>Cancelar</Button>
            <Button type="submit" variant="gold" loading={isSubmitting}>Guardar</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
