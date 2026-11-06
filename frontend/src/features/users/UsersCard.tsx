import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AlertCircle, KeyRound, Plus, Power, UsersRound } from "lucide-react";

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
import { ErrorMessage } from "@/components/common/ErrorMessage";
import { useAuth } from "@/features/auth";
import { useCreateUser, useResetPassword, useUpdateUser, useUsers } from "@/hooks/useUsers";
import { toast } from "@/hooks/useToast";
import { getErrorMessage } from "@/lib/axios";
import { ROLE_LABELS } from "@/lib/labels";
import { reportError } from "@/lib/report-error";
import type { StaffUser, UserRole } from "@/types";

const STAFF_ROLES: UserRole[] = ["admin", "receptionist", "trainer"];
const password = z.string().min(8, "Mínimo 8 caracteres").max(72, "Máximo 72 caracteres");

const newUserSchema = z.object({
  full_name: z.string().trim().min(2, "Mínimo 2 caracteres").max(255),
  email: z.string().trim().email("Correo inválido"),
  role: z.enum(["admin", "receptionist", "trainer"]),
  password,
});
type NewUserValues = z.infer<typeof newUserSchema>;

function NewUserDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const create = useCreateUser();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<NewUserValues>({
    resolver: zodResolver(newUserSchema),
    defaultValues: { full_name: "", email: "", role: "receptionist", password: "" },
  });
  const onSubmit = async (v: NewUserValues) => {
    setError(null);
    try {
      const u = await create.mutateAsync(v);
      toast({ variant: "success", title: "Usuario creado", description: `${u.full_name} · ${ROLE_LABELS[u.role]}` });
      reset();
      onOpenChange(false);
    } catch (err) {
      setError(reportError(err, "No se pudo crear el usuario"));
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Nuevo usuario</DialogTitle>
          <DialogDescription>Cuenta para el personal del gimnasio. Entréguele la contraseña en persona.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          {error && <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}><AlertDescription className="text-foreground">{error}</AlertDescription></Alert>}
          <div className="space-y-1.5">
            <Label htmlFor="nu-name">Nombre completo</Label>
            <Input id="nu-name" autoFocus {...register("full_name")} />
            {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="nu-email">Correo</Label>
            <Input id="nu-email" type="email" autoComplete="off" {...register("email")} />
            {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="nu-role">Rol</Label>
              <Select id="nu-role" {...register("role")}>
                {STAFF_ROLES.map((r) => <option key={r} value={r}>{ROLE_LABELS[r]}</option>)}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="nu-pass">Contraseña</Label>
              <Input id="nu-pass" type="password" autoComplete="new-password" {...register("password")} />
              {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={isSubmitting}>Cancelar</Button>
            <Button type="submit" variant="gold" loading={isSubmitting}>Crear usuario</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

const resetSchema = z.object({ password });
type ResetValues = z.infer<typeof resetSchema>;

function ResetPasswordDialog({ user, onClose }: { user: StaffUser | null; onClose: () => void }) {
  const resetPassword = useResetPassword();
  const [error, setError] = useState<string | null>(null);
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<ResetValues>({
    resolver: zodResolver(resetSchema), defaultValues: { password: "" },
  });
  const close = () => { reset(); setError(null); onClose(); };
  const onSubmit = async (v: ResetValues) => {
    if (!user) return;
    setError(null);
    try {
      await resetPassword.mutateAsync({ id: user.id, password: v.password });
      toast({ variant: "success", title: "Contraseña actualizada", description: `${user.full_name} debe iniciar sesión de nuevo.` });
      close();
    } catch (err) {
      setError(reportError(err, "No se pudo cambiar la contraseña"));
    }
  };
  return (
    <Dialog open={user !== null} onOpenChange={(o) => !o && close()}>
      <DialogContent className="max-w-sm">
        <DialogHeader>
          <DialogTitle>Nueva contraseña</DialogTitle>
          <DialogDescription>{user?.full_name}: sus sesiones abiertas se cerrarán.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
          {error && <Alert variant="destructive" icon={<AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />}><AlertDescription className="text-foreground">{error}</AlertDescription></Alert>}
          <div className="space-y-1.5">
            <Label htmlFor="rp-pass">Contraseña nueva</Label>
            <Input id="rp-pass" type="password" autoFocus autoComplete="new-password" {...register("password")} />
            {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
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

/** Usuarios del gimnasio: crear, cambiar rol, activar/desactivar y restablecer contraseña. */
export function UsersCard() {
  const { user: me } = useAuth();
  const users = useUsers();
  const update = useUpdateUser();
  const [creating, setCreating] = useState(false);
  const [resetting, setResetting] = useState<StaffUser | null>(null);

  const change = async (u: StaffUser, payload: { role?: UserRole; is_active?: boolean }, done: string) => {
    try {
      await update.mutateAsync({ id: u.id, payload });
      toast({ variant: "success", title: done, description: u.full_name });
    } catch (err) {
      reportError(err, "No se pudo actualizar el usuario");
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="flex items-center gap-2 text-base"><UsersRound className="h-4 w-4 text-gold" aria-hidden /> Usuarios</CardTitle>
        <Button size="sm" variant="gold" onClick={() => setCreating(true)}><Plus className="mr-1.5 h-4 w-4" aria-hidden /> Nuevo usuario</Button>
      </CardHeader>
      <CardContent>
        {users.isLoading ? <Skeleton className="h-32" /> : users.isError ? (
          <ErrorMessage title="No se pudieron cargar los usuarios" message={getErrorMessage(users.error)} />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead className="hidden md:table-cell">Correo</TableHead>
                <TableHead>Rol</TableHead>
                <TableHead>Estado</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.data?.map((u) => {
                const isMe = u.id === me?.id;
                return (
                  <TableRow key={u.id} className={u.is_active ? undefined : "opacity-60"}>
                    <TableCell className="font-medium">{u.full_name}{isMe && <span className="ml-1 text-xs text-muted-foreground">(usted)</span>}</TableCell>
                    <TableCell className="hidden text-muted-foreground md:table-cell">{u.email}</TableCell>
                    <TableCell>
                      <Select aria-label={`Rol de ${u.full_name}`} value={u.role} disabled={isMe || update.isPending}
                        onChange={(e) => void change(u, { role: e.target.value as UserRole }, "Rol actualizado")}>
                        {(STAFF_ROLES.includes(u.role) ? STAFF_ROLES : [...STAFF_ROLES, u.role]).map((r) => (
                          <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                        ))}
                      </Select>
                    </TableCell>
                    <TableCell>{u.is_active ? <Badge variant="success">Activo</Badge> : <Badge variant="destructive">Desactivado</Badge>}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button size="sm" variant="ghost" onClick={() => setResetting(u)} title="Asignar contraseña nueva">
                          <KeyRound className="h-4 w-4" aria-hidden /><span className="sr-only">Contraseña</span>
                        </Button>
                        {!isMe && (
                          <Button size="sm" variant="ghost" disabled={update.isPending}
                            onClick={() => void change(u, { is_active: !u.is_active }, u.is_active ? "Usuario desactivado" : "Usuario activado")}
                            title={u.is_active ? "Desactivar (cierra sus sesiones)" : "Activar"}>
                            <Power className="h-4 w-4" aria-hidden /><span className="sr-only">{u.is_active ? "Desactivar" : "Activar"}</span>
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        )}
      </CardContent>
      <NewUserDialog open={creating} onOpenChange={setCreating} />
      <ResetPasswordDialog user={resetting} onClose={() => setResetting(null)} />
    </Card>
  );
}
